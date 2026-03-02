"""JSON-backed adapter for checkpoint persistence."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.domain.services.checkpoint_store import CheckpointStore
from cvcutter.shared.types import CheckpointStatus, PipelineStage

_STAGE_ORDER = {stage: index for index, stage in enumerate(PipelineStage)}


class JsonCheckpointStore(CheckpointStore):
    """Persist and load project checkpoints as JSON files."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize the store with the per-user app data base directory."""
        self._base_dir = Path(base_dir)

    def save(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint record."""
        checkpoint_path = self._checkpoint_path(
            checkpoint.project_id,
            checkpoint.stage,
            checkpoint.segment_index,
        )
        self._write_json(checkpoint_path, asdict(checkpoint))

    def load(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None = None,
    ) -> Checkpoint | None:
        """Load a checkpoint for the specified stage and optional segment index."""
        payload = self._read_json(self._checkpoint_path(project_id, stage, segment_index))
        if not isinstance(payload, dict):
            return None
        return self._checkpoint_from_raw(payload)

    def load_all(self, project_id: str) -> list[Checkpoint]:
        """Load all checkpoints for a project in deterministic stage order."""
        checkpoint_dir = self._checkpoint_dir(project_id)
        if not checkpoint_dir.exists():
            return []

        checkpoints: list[Checkpoint] = []
        for checkpoint_path in checkpoint_dir.glob("*.json"):
            payload = self._read_json(checkpoint_path)
            if not isinstance(payload, dict):
                continue
            checkpoint = self._checkpoint_from_raw(payload)
            if checkpoint is not None:
                checkpoints.append(checkpoint)

        checkpoints.sort(
            key=lambda checkpoint: (
                _STAGE_ORDER.get(checkpoint.stage, len(_STAGE_ORDER)),
                checkpoint.segment_index if checkpoint.segment_index is not None else -1,
                str(checkpoint.id),
            ),
        )
        return checkpoints

    def invalidate(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None = None,
        cascade: bool = True,
    ) -> list[str]:
        """Mark matching checkpoint records as INVALIDATED and return affected IDs."""
        del cascade
        checkpoint_dir = self._checkpoint_dir(project_id)
        if not checkpoint_dir.exists():
            return []

        stage_name = stage.value.lower()
        if segment_index is None:
            targets = [
                checkpoint_dir / f"{stage_name}.json",
                *sorted(checkpoint_dir.glob(f"{stage_name}_*.json")),
            ]
        else:
            targets = [checkpoint_dir / f"{stage_name}_{segment_index}.json"]

        invalidated_ids: list[str] = []
        for target in targets:
            payload = self._read_json(target)
            if not isinstance(payload, dict):
                continue

            payload["status"] = CheckpointStatus.INVALIDATED.value
            self._write_json(target, payload)
            checkpoint_id = payload.get("id")
            if checkpoint_id is not None:
                invalidated_ids.append(str(checkpoint_id))
        return invalidated_ids

    def clean_completed(self, project_id: str) -> int:
        """Delete checkpoint JSON artifacts for a completed project."""
        checkpoint_dir = self._checkpoint_dir(project_id)
        if not checkpoint_dir.exists():
            return 0

        cleaned = 0
        for checkpoint_file in checkpoint_dir.glob("*.json"):
            try:
                checkpoint_file.unlink()
            except OSError:
                continue
            cleaned += 1
        return cleaned

    def _checkpoint_dir(self, project_id: str) -> Path:
        """Return the checkpoint directory for a project."""
        return self._base_dir / "projects" / project_id / "checkpoints"

    def _checkpoint_path(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None,
    ) -> Path:
        """Build checkpoint file path using the stage naming convention."""
        stage_name = stage.value.lower()
        file_name = (
            f"{stage_name}_{segment_index}.json"
            if segment_index is not None
            else f"{stage_name}.json"
        )
        return self._checkpoint_dir(project_id) / file_name

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse datetime values from persisted JSON payload."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        """Normalize optional text fields from JSON payloads."""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _checkpoint_from_raw(self, raw: dict[str, Any]) -> Checkpoint | None:
        """Build a Checkpoint from raw JSON payload."""
        input_hashes = raw.get("input_hashes")
        config_snapshot = raw.get("config_snapshot")
        model_versions = raw.get("model_versions")
        if not isinstance(input_hashes, dict):
            return None
        if not isinstance(config_snapshot, dict):
            return None
        if not isinstance(model_versions, dict):
            return None

        output_references_raw = raw.get("output_references")
        output_references = (
            [str(item) for item in output_references_raw]
            if isinstance(output_references_raw, list)
            else []
        )
        created_at = self._parse_datetime(raw.get("created_at"))
        if created_at is None:
            return None

        try:
            segment_index_raw = raw.get("segment_index")
            segment_index = None if segment_index_raw is None else int(segment_index_raw)
            return Checkpoint(
                id=UUID(str(raw.get("id"))),
                project_id=str(raw.get("project_id", "")),
                stage=PipelineStage(str(raw.get("stage"))),
                status=CheckpointStatus(
                    str(raw.get("status", CheckpointStatus.VALID.value)),
                ),
                created_at=created_at,
                input_hashes={str(key): str(value) for key, value in input_hashes.items()},
                config_snapshot=dict(config_snapshot),
                model_versions={str(key): str(value) for key, value in model_versions.items()},
                output_references=output_references,
                segment_index=segment_index,
                error_detail=self._optional_text(raw.get("error_detail")),
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        """Safely write JSON data to disk."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError):
            return

    @staticmethod
    def _read_json(path: Path) -> Any | None:
        """Safely read JSON data from disk."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
