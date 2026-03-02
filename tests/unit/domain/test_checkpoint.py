"""Unit tests for checkpoint domain entity behavior (T104)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.shared.types import CheckpointStatus, PipelineStage
from tests.conftest import make_checkpoint_dict, make_project_config, make_project_id


def _to_checkpoint(raw: dict[str, Any]) -> Checkpoint:
    input_hashes_raw = raw.get("input_hashes")
    model_versions_raw = raw.get("model_versions")
    output_references_raw = raw.get("output_references")
    config_snapshot_raw = raw.get("config_snapshot")
    segment_index_raw = raw.get("segment_index")
    error_detail_raw = raw.get("error_detail")

    return Checkpoint(
        id=UUID(str(raw["id"])),
        project_id=str(raw["project_id"]),
        stage=PipelineStage(str(raw["stage"])),
        status=CheckpointStatus(str(raw["status"])),
        created_at=datetime.fromisoformat(str(raw["created_at"])),
        input_hashes=(
            {str(key): str(value) for key, value in input_hashes_raw.items()}
            if isinstance(input_hashes_raw, dict)
            else {}
        ),
        config_snapshot=dict(config_snapshot_raw) if isinstance(config_snapshot_raw, dict) else {},
        model_versions=(
            {str(key): str(value) for key, value in model_versions_raw.items()}
            if isinstance(model_versions_raw, dict)
            else {}
        ),
        output_references=[str(item) for item in output_references_raw]
        if isinstance(output_references_raw, list)
        else [],
        segment_index=segment_index_raw if isinstance(segment_index_raw, int) else None,
        error_detail=str(error_detail_raw) if error_detail_raw else None,
    )


def test_checkpoint_creation_with_required_fields() -> None:
    raw = make_checkpoint_dict(
        project_id=make_project_id(),
        stage=PipelineStage.DETECTION.value,
        status=CheckpointStatus.VALID.value,
        config_snapshot=make_project_config(),
    )

    checkpoint = _to_checkpoint(raw)

    assert checkpoint.project_id == raw["project_id"]
    assert checkpoint.stage == PipelineStage.DETECTION
    assert checkpoint.status == CheckpointStatus.VALID


def test_checkpoint_invalidate_sets_status_to_invalidated() -> None:
    checkpoint = _to_checkpoint(
        make_checkpoint_dict(
            project_id=make_project_id(),
            stage=PipelineStage.AUDIO_SYNC.value,
            status=CheckpointStatus.VALID.value,
            config_snapshot=make_project_config(),
        ),
    )

    checkpoint.invalidate()

    assert checkpoint.status == CheckpointStatus.INVALIDATED


def test_checkpoint_is_valid_returns_true_for_valid_status() -> None:
    checkpoint = _to_checkpoint(
        make_checkpoint_dict(
            project_id=make_project_id(),
            stage=PipelineStage.EXPORT.value,
            status=CheckpointStatus.VALID.value,
            config_snapshot=make_project_config(),
        ),
    )

    assert checkpoint.is_valid() is True


def test_checkpoint_supports_segment_index() -> None:
    raw = make_checkpoint_dict(
        project_id=make_project_id(),
        stage=PipelineStage.EXPORT.value,
        status=CheckpointStatus.VALID.value,
        config_snapshot=make_project_config(),
    )
    raw["segment_index"] = 4

    checkpoint = _to_checkpoint(raw)

    assert checkpoint.segment_index == 4


def test_checkpoint_supports_error_detail() -> None:
    raw = make_checkpoint_dict(
        project_id=make_project_id(),
        stage=PipelineStage.EXPORT.value,
        status=CheckpointStatus.INVALIDATED.value,
        config_snapshot=make_project_config(),
    )
    raw["error_detail"] = "ffmpeg export failed on segment 4"

    checkpoint = _to_checkpoint(raw)

    assert checkpoint.error_detail == "ffmpeg export failed on segment 4"
