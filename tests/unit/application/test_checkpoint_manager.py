"""Unit tests for checkpoint dependency and validation behavior.

These tests cover cascade invalidation rules, deterministic graph traversal,
resume-point selection, and strict checkpoint validation semantics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from cvcutter.application.checkpoint_manager import CheckpointManager
from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.shared.types import CheckpointStatus, PipelineStage
from tests.conftest import make_project_config


class MockCheckpointStore:
    """In-memory checkpoint-store test double."""

    def __init__(self, checkpoints: list[Checkpoint] | None = None) -> None:
        """Initialize the mock with optional preloaded checkpoints."""
        self._checkpoints = list(checkpoints or [])
        self.invalidate_calls: list[tuple[str, PipelineStage, int | None, bool]] = []

    def save(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint into memory."""
        self._checkpoints.append(checkpoint)

    def load(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None = None,
    ) -> Checkpoint | None:
        """Load the first matching checkpoint, if present."""
        for checkpoint in self._checkpoints:
            if (
                checkpoint.project_id == project_id
                and checkpoint.stage == stage
                and checkpoint.segment_index == segment_index
            ):
                return checkpoint
        return None

    def load_all(self, project_id: str) -> list[Checkpoint]:
        """Load all checkpoints for a project."""
        return [checkpoint for checkpoint in self._checkpoints if checkpoint.project_id == project_id]

    def invalidate(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None = None,
        cascade: bool = True,
    ) -> list[str]:
        """Track invalidation call and return deterministic checkpoint IDs."""
        self.invalidate_calls.append((project_id, stage, segment_index, cascade))
        invalidated_ids: list[str] = []
        for checkpoint in self._checkpoints:
            if checkpoint.project_id != project_id or checkpoint.stage != stage:
                continue
            if segment_index is not None and checkpoint.segment_index != segment_index:
                continue
            checkpoint.status = CheckpointStatus.INVALIDATED
            invalidated_ids.append(str(checkpoint.id))
        return invalidated_ids or [f"{stage.value.lower()}-checkpoint"]

    def clean_completed(self, project_id: str) -> int:
        """No-op cleanup implementation for protocol completeness."""
        return 0


def _make_checkpoint(
    *,
    project_id: str,
    stage: PipelineStage,
    status: CheckpointStatus = CheckpointStatus.VALID,
    input_hashes: dict[str, str] | None = None,
    config_snapshot: dict | None = None,
    model_versions: dict[str, str] | None = None,
    segment_index: int | None = None,
) -> Checkpoint:
    """Create a valid checkpoint entity for tests."""
    return Checkpoint(
        id=uuid4(),
        project_id=project_id,
        stage=stage,
        status=status,
        created_at=datetime.now(UTC),
        input_hashes=input_hashes or {"input.mp4": "abc123"},
        config_snapshot=config_snapshot or make_project_config(),
        model_versions=model_versions or {"yolov8n": "v8.0.0"},
        segment_index=segment_index,
    )


def test_invalidating_detection_cascades_to_export_mapping_and_upload() -> None:
    """Invalidating DETECTION should cascade through downstream execution stages."""
    store = MockCheckpointStore()
    manager = CheckpointManager(store)

    invalidated = manager.invalidate_with_cascade("project-1", PipelineStage.DETECTION)

    called_stages = [stage for _, stage, _, _ in store.invalidate_calls]
    assert called_stages == [
        PipelineStage.DETECTION,
        PipelineStage.EXPORT,
        PipelineStage.MAPPING,
        PipelineStage.UPLOAD,
    ]
    assert invalidated == [
        "detection-checkpoint",
        "export-checkpoint",
        "mapping-checkpoint",
        "upload-checkpoint",
    ]


def test_invalidating_audio_sync_cascades_without_touching_detection() -> None:
    """Invalidating AUDIO_SYNC should not cascade upstream into DETECTION."""
    store = MockCheckpointStore()
    manager = CheckpointManager(store)

    manager.invalidate_with_cascade("project-1", PipelineStage.AUDIO_SYNC)

    called_stages = [stage for _, stage, _, _ in store.invalidate_calls]
    assert called_stages == [
        PipelineStage.AUDIO_SYNC,
        PipelineStage.EXPORT,
        PipelineStage.MAPPING,
        PipelineStage.UPLOAD,
    ]
    assert PipelineStage.DETECTION not in called_stages


def test_invalidating_concatenation_cascades_to_all_downstream_stages() -> None:
    """Invalidating CONCATENATION should invalidate every downstream stage."""
    store = MockCheckpointStore()
    manager = CheckpointManager(store)

    manager.invalidate_with_cascade("project-1", PipelineStage.CONCATENATION)

    called_stages = [stage for _, stage, _, _ in store.invalidate_calls]
    assert called_stages == [
        PipelineStage.CONCATENATION,
        PipelineStage.DETECTION,
        PipelineStage.AUDIO_SYNC,
        PipelineStage.EXPORT,
        PipelineStage.MAPPING,
        PipelineStage.UPLOAD,
    ]


def test_segment_scoped_invalidation_does_not_apply_segment_scope_to_downstream_stages() -> None:
    """Downstream cascade should invalidate full stage scope after segment-scoped root invalidation."""
    store = MockCheckpointStore()
    manager = CheckpointManager(store)

    manager.invalidate_with_cascade("project-1", PipelineStage.EXPORT, segment_index=2)

    assert store.invalidate_calls == [
        ("project-1", PipelineStage.EXPORT, 2, False),
        ("project-1", PipelineStage.MAPPING, None, False),
        ("project-1", PipelineStage.UPLOAD, None, False),
    ]


def test_cascade_invalidation_order_is_deterministic() -> None:
    """Downstream traversal should return a stable deterministic order."""
    manager = CheckpointManager(MockCheckpointStore())

    first = manager.get_downstream_stages(PipelineStage.CONCATENATION)
    second = manager.get_downstream_stages(PipelineStage.CONCATENATION)

    assert first == second
    assert first == [
        PipelineStage.DETECTION,
        PipelineStage.AUDIO_SYNC,
        PipelineStage.EXPORT,
        PipelineStage.MAPPING,
        PipelineStage.UPLOAD,
    ]


def test_find_resume_point_returns_earliest_valid_stage() -> None:
    """Resume point should be the earliest stage in execution order that is valid."""
    project_id = "project-1"
    store = MockCheckpointStore(
        checkpoints=[
            _make_checkpoint(
                project_id=project_id,
                stage=PipelineStage.DETECTION,
                status=CheckpointStatus.INVALIDATED,
            ),
            _make_checkpoint(project_id=project_id, stage=PipelineStage.MAPPING),
            _make_checkpoint(project_id=project_id, stage=PipelineStage.AUDIO_SYNC),
            _make_checkpoint(project_id=project_id, stage=PipelineStage.UPLOAD),
        ],
    )
    manager = CheckpointManager(store)

    resume_stage = manager.find_resume_point(project_id)

    assert resume_stage == PipelineStage.AUDIO_SYNC


def test_validate_checkpoint_detects_hash_mismatches() -> None:
    """Checkpoint validation should fail when input hashes differ."""
    checkpoint = _make_checkpoint(
        project_id="project-1",
        stage=PipelineStage.EXPORT,
        input_hashes={"input.mp4": "expected-hash"},
    )
    manager = CheckpointManager(MockCheckpointStore())

    is_valid = manager.validate_checkpoint(
        checkpoint=checkpoint,
        current_input_hashes={"input.mp4": "different-hash"},
        current_config=make_project_config(),
        current_model_versions={"yolov8n": "v8.0.0"},
    )

    assert is_valid is False


def test_make_resume_decision_invalidates_cascade_on_config_hash_mismatch() -> None:
    """Config snapshot mismatch should invalidate originating and downstream stages."""
    project_id = "project-1"
    store = MockCheckpointStore(
        checkpoints=[
            _make_checkpoint(project_id=project_id, stage=PipelineStage.CONCATENATION),
            _make_checkpoint(project_id=project_id, stage=PipelineStage.DETECTION),
            _make_checkpoint(project_id=project_id, stage=PipelineStage.AUDIO_SYNC),
        ],
    )
    manager = CheckpointManager(store)

    decision = manager.make_resume_decision(
        project_id=project_id,
        current_input_hashes={"input.mp4": "abc123"},
        current_config=make_project_config(output_quality="low"),
        current_model_versions={"yolov8n": "v8.0.0"},
    )

    assert decision.can_resume is False
    assert decision.resume_stage is None
    assert PipelineStage.CONCATENATION in decision.invalidated_stages
    assert decision.reasons[PipelineStage.CONCATENATION] == "config_hash_mismatch"


def test_make_resume_decision_invalidates_cascade_on_model_version_mismatch() -> None:
    """Model-version mismatch should invalidate the mismatched stage cascade."""
    project_id = "project-1"
    concat = _make_checkpoint(
        project_id=project_id,
        stage=PipelineStage.CONCATENATION,
        model_versions={"video_io": "MockVideoIO"},
    )
    detection = _make_checkpoint(
        project_id=project_id,
        stage=PipelineStage.DETECTION,
        input_hashes={"concat.mp4": "hash"},
        model_versions={"audio_energy_detector": "v1"},
    )
    store = MockCheckpointStore(checkpoints=[concat, detection])
    manager = CheckpointManager(store)

    decision = manager.make_resume_decision(
        project_id=project_id,
        current_input_hashes={
            PipelineStage.CONCATENATION.value: {"input.mp4": "abc123"},
            PipelineStage.DETECTION.value: {"concat.mp4": "hash"},
        },
        current_config={stage.value: make_project_config() for stage in PipelineStage},
        current_model_versions={
            PipelineStage.CONCATENATION.value: {"video_io": "MockVideoIO"},
            PipelineStage.DETECTION.value: {"audio_energy_detector": "v2"},
        },
    )

    assert decision.can_resume is True
    assert decision.resume_stage == PipelineStage.CONCATENATION
    assert PipelineStage.DETECTION in decision.invalidated_stages
    assert decision.reasons[PipelineStage.DETECTION] == "model_version_mismatch"


def test_find_resume_point_with_mixed_valid_and_invalid_checkpoints() -> None:
    """Mixed checkpoint statuses should resolve to earliest valid stage only."""
    project_id = "project-1"
    store = MockCheckpointStore(
        checkpoints=[
            _make_checkpoint(
                project_id=project_id,
                stage=PipelineStage.CONCATENATION,
                status=CheckpointStatus.INVALIDATED,
            ),
            _make_checkpoint(project_id=project_id, stage=PipelineStage.DETECTION),
            _make_checkpoint(
                project_id=project_id,
                stage=PipelineStage.AUDIO_SYNC,
                status=CheckpointStatus.INVALIDATED,
            ),
            _make_checkpoint(project_id=project_id, stage=PipelineStage.EXPORT),
        ],
    )
    manager = CheckpointManager(store)

    assert manager.find_resume_point(project_id) == PipelineStage.DETECTION


def test_make_resume_decision_returns_resume_stage_when_valid_checkpoints_exist() -> None:
    """Resume decision should point at earliest valid stage when resume is possible."""
    project_id = "project-1"
    store = MockCheckpointStore(
        checkpoints=[
            _make_checkpoint(project_id=project_id, stage=PipelineStage.CONCATENATION),
            _make_checkpoint(project_id=project_id, stage=PipelineStage.DETECTION),
        ],
    )
    manager = CheckpointManager(store)

    decision = manager.make_resume_decision(
        project_id=project_id,
        current_input_hashes={"input.mp4": "abc123"},
        current_config=make_project_config(),
        current_model_versions={"yolov8n": "v8.0.0"},
    )

    assert decision.can_resume is True
    assert decision.resume_stage == PipelineStage.CONCATENATION


def test_make_resume_decision_keeps_latest_matching_checkpoint_when_older_is_stale() -> None:
    """Older stale checkpoints should not invalidate a stage if a newer one is valid."""
    project_id = "project-1"
    stale = _make_checkpoint(
        project_id=project_id,
        stage=PipelineStage.CONCATENATION,
        input_hashes={"input.mp4": "old-hash"},
    )
    current = _make_checkpoint(
        project_id=project_id,
        stage=PipelineStage.CONCATENATION,
        input_hashes={"input.mp4": "current-hash"},
    )
    store = MockCheckpointStore(checkpoints=[stale, current])
    manager = CheckpointManager(store)

    decision = manager.make_resume_decision(
        project_id=project_id,
        current_input_hashes={"input.mp4": "current-hash"},
        current_config=make_project_config(),
        current_model_versions={"yolov8n": "v8.0.0"},
    )

    assert decision.can_resume is True
    assert decision.resume_stage == PipelineStage.CONCATENATION
    assert decision.invalidated_stages == []
