"""Checkpoint dependency graph management and resume helpers."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cvcutter.shared.types import CheckpointStatus, PipelineStage

if TYPE_CHECKING:
    from cvcutter.domain.models.checkpoint import Checkpoint
    from cvcutter.domain.services.checkpoint_store import CheckpointStore

logger = logging.getLogger(__name__)

STAGE_DEPENDENCIES: dict[PipelineStage, set[PipelineStage]] = {
    PipelineStage.CONCATENATION: {PipelineStage.DETECTION, PipelineStage.AUDIO_SYNC},
    PipelineStage.DETECTION: {PipelineStage.EXPORT},
    PipelineStage.AUDIO_SYNC: {PipelineStage.EXPORT},
    PipelineStage.EXPORT: {PipelineStage.MAPPING},
    PipelineStage.MAPPING: {PipelineStage.UPLOAD},
    PipelineStage.UPLOAD: set(),
}

_STAGE_EXECUTION_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.CONCATENATION,
    PipelineStage.DETECTION,
    PipelineStage.AUDIO_SYNC,
    PipelineStage.EXPORT,
    PipelineStage.MAPPING,
    PipelineStage.UPLOAD,
)
_STAGE_ORDER_INDEX = {stage: index for index, stage in enumerate(_STAGE_EXECUTION_ORDER)}


@dataclass(frozen=True)
class ResumeDecision:
    """Structured resume decision derived from persisted checkpoints."""

    can_resume: bool
    resume_stage: PipelineStage | None
    invalidated_stages: list[PipelineStage]
    reasons: dict[PipelineStage, str]


class CheckpointManager:
    """Coordinate checkpoint validation, invalidation, and resume lookup."""

    def __init__(self, checkpoint_store: CheckpointStore) -> None:
        """Initialize with a checkpoint persistence store."""
        self._checkpoint_store = checkpoint_store

    def validate_checkpoint(
        self,
        checkpoint: Checkpoint,
        current_input_hashes: dict[str, str],
        current_config: dict,
        current_model_versions: dict[str, str],
    ) -> bool:
        """Return True when a checkpoint is valid for the current inputs/config/models."""
        return (
            self._validation_reason(
                checkpoint=checkpoint,
                current_input_hashes=current_input_hashes,
                current_config=current_config,
                current_model_versions=current_model_versions,
            )
            is None
        )

    def make_resume_decision(
        self,
        project_id: str,
        current_input_hashes: dict,
        current_config: dict,
        current_model_versions: dict,
    ) -> ResumeDecision:
        """Build resume/restart decision by validating checkpoints in execution order."""
        checkpoints = self._checkpoint_store.load_all(project_id)
        invalidated_stages: list[PipelineStage] = []
        seen_invalidations: set[PipelineStage] = set()
        reasons: dict[PipelineStage, str] = {}

        for stage in _STAGE_EXECUTION_ORDER:
            stage_checkpoints = [
                checkpoint
                for checkpoint in checkpoints
                if checkpoint.stage == stage and checkpoint.status == CheckpointStatus.VALID
            ]
            if not stage_checkpoints:
                continue

            stage_input_hashes = self._stage_scope_payload(current_input_hashes, stage)
            stage_config = self._stage_scope_payload(current_config, stage)
            stage_model_versions = self._stage_scope_payload(current_model_versions, stage)

            stage_reason: str | None = None
            stage_has_valid_checkpoint = False
            for checkpoint in stage_checkpoints:
                checkpoint_input_hashes = self._segment_scope_payload(
                    stage_input_hashes,
                    checkpoint.segment_index,
                )
                reason = self._validation_reason(
                    checkpoint=checkpoint,
                    current_input_hashes=checkpoint_input_hashes,
                    current_config=stage_config,
                    current_model_versions=stage_model_versions,
                )
                if reason is None:
                    stage_has_valid_checkpoint = True
                    break
                stage_reason = reason

            if stage_has_valid_checkpoint:
                continue

            if stage_reason is None:
                stage_reason = "no_valid_checkpoint"
            reasons[stage] = stage_reason
            self.invalidate_with_cascade(project_id, stage)
            for invalidated in [stage, *self.get_downstream_stages(stage)]:
                if invalidated in seen_invalidations:
                    continue
                seen_invalidations.add(invalidated)
                invalidated_stages.append(invalidated)
                reasons.setdefault(
                    invalidated,
                    f"invalidated_by_{stage.value.lower()}",
                )

        resume_stage = self.find_resume_point(project_id)
        if resume_stage is not None:
            reasons.setdefault(resume_stage, "valid_checkpoint_available")

        return ResumeDecision(
            can_resume=resume_stage is not None,
            resume_stage=resume_stage,
            invalidated_stages=invalidated_stages,
            reasons=reasons,
        )

    def get_downstream_stages(self, stage: PipelineStage) -> list[PipelineStage]:
        """Return transitive downstream stages from the dependency graph."""
        downstream_stages: list[PipelineStage] = []
        visited: set[PipelineStage] = set()
        pending = deque(self._sort_stages(STAGE_DEPENDENCIES.get(stage, set())))

        while pending:
            current_stage = pending.popleft()
            if current_stage in visited:
                continue
            visited.add(current_stage)
            downstream_stages.append(current_stage)

            for next_stage in self._sort_stages(STAGE_DEPENDENCIES.get(current_stage, set())):
                if next_stage not in visited:
                    pending.append(next_stage)

        return downstream_stages

    def invalidate_with_cascade(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None = None,
    ) -> list[str]:
        """Invalidate a stage and all transitive downstream stages."""
        stages_to_invalidate = [stage, *self.get_downstream_stages(stage)]
        logger.info(
            "Cascade invalidation requested: project_id=%s stage=%s segment_index=%s targets=%s",
            project_id,
            stage,
            segment_index,
            [target.value for target in stages_to_invalidate],
        )

        invalidated_checkpoint_ids: list[str] = []
        seen_checkpoint_ids: set[str] = set()

        for target_stage in stages_to_invalidate:
            target_segment_index = segment_index if target_stage == stage else None
            stage_invalidated_ids = self._checkpoint_store.invalidate(
                project_id=project_id,
                stage=target_stage,
                segment_index=target_segment_index,
                cascade=False,
            )

            if stage_invalidated_ids:
                logger.info(
                    "Invalidated checkpoints: project_id=%s stage=%s segment_index=%s count=%d",
                    project_id,
                    target_stage,
                    target_segment_index,
                    len(stage_invalidated_ids),
                )
            else:
                logger.debug(
                    "No checkpoints invalidated: project_id=%s stage=%s segment_index=%s",
                    project_id,
                    target_stage,
                    target_segment_index,
                )

            for checkpoint_id in stage_invalidated_ids:
                if checkpoint_id in seen_checkpoint_ids:
                    continue
                seen_checkpoint_ids.add(checkpoint_id)
                invalidated_checkpoint_ids.append(checkpoint_id)

        return invalidated_checkpoint_ids

    def find_resume_point(self, project_id: str) -> PipelineStage | None:
        """Find the earliest stage with a valid checkpoint for the project."""
        checkpoints = self._checkpoint_store.load_all(project_id)
        valid_stages = {
            checkpoint.stage
            for checkpoint in checkpoints
            if checkpoint.status == CheckpointStatus.VALID
        }

        for stage in _STAGE_EXECUTION_ORDER:
            if stage in valid_stages:
                return stage
        return None

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint record."""
        self._checkpoint_store.save(checkpoint)

    def load_all_checkpoints(self, project_id: str) -> list[Checkpoint]:
        """Load every checkpoint record for a project."""
        return self._checkpoint_store.load_all(project_id)

    @staticmethod
    def _sort_stages(stages: set[PipelineStage]) -> list[PipelineStage]:
        """Sort stages in deterministic pipeline execution order."""
        return sorted(stages, key=_STAGE_ORDER_INDEX.__getitem__)

    @staticmethod
    def _stage_scope_payload(payload: dict[str, Any], stage: PipelineStage) -> dict[str, Any]:
        """Resolve optional stage-scoped payload dictionaries."""
        scoped = payload.get(stage.value)
        return scoped if isinstance(scoped, dict) else payload

    @staticmethod
    def _segment_scope_payload(payload: dict[str, Any], segment_index: int | None) -> dict[str, Any]:
        """Resolve optional segment-scoped payload dictionaries."""
        if segment_index is None:
            return payload
        scoped = payload.get(f"segment:{segment_index}")
        return scoped if isinstance(scoped, dict) else payload

    def _validation_reason(
        self,
        checkpoint: Checkpoint,
        current_input_hashes: dict[str, Any],
        current_config: dict[str, Any],
        current_model_versions: dict[str, Any],
    ) -> str | None:
        """Return mismatch reason or None when checkpoint remains valid."""
        if checkpoint.status != CheckpointStatus.VALID:
            return "checkpoint_status_mismatch"
        if self._fingerprint(checkpoint.input_hashes) != self._fingerprint(current_input_hashes):
            return "input_hash_mismatch"
        if not self._snapshot_matches(checkpoint.config_snapshot, current_config):
            return "config_hash_mismatch"
        if self._fingerprint(checkpoint.model_versions) != self._fingerprint(current_model_versions):
            return "model_version_mismatch"
        return None

    @staticmethod
    def _fingerprint(payload: dict[str, Any]) -> str:
        """Build deterministic content fingerprint for hash-based checkpoint comparisons."""
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _snapshot_matches(
        self,
        checkpoint_snapshot: dict[str, Any],
        current_snapshot: dict[str, Any],
    ) -> bool:
        """Compare full or scoped config snapshots for checkpoint validation."""
        if set(current_snapshot).issubset(checkpoint_snapshot):
            scoped_snapshot = {key: checkpoint_snapshot[key] for key in current_snapshot}
            return self._fingerprint(scoped_snapshot) == self._fingerprint(current_snapshot)
        return self._fingerprint(checkpoint_snapshot) == self._fingerprint(current_snapshot)
