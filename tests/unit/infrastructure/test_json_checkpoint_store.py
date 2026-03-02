"""Unit tests for JSON checkpoint persistence lifecycle behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.infrastructure.persistence.json_checkpoint_store import JsonCheckpointStore
from cvcutter.shared.types import CheckpointStatus, PipelineStage
from tests.conftest import make_project_config, make_project_id


def _make_checkpoint(
    project_id: str,
    *,
    stage: PipelineStage,
    segment_index: int | None = None,
) -> Checkpoint:
    return Checkpoint(
        id=uuid4(),
        project_id=project_id,
        stage=stage,
        status=CheckpointStatus.VALID,
        created_at=datetime.now(UTC),
        input_hashes={"input.mp4": "hash"},
        config_snapshot=make_project_config(),
        model_versions={"detector": "v1"},
        output_references=["out.mp4"],
        segment_index=segment_index,
    )


def test_checkpoint_lifecycle_save_load_invalidate_and_reload(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path)
    project_id = make_project_id()
    checkpoint = _make_checkpoint(project_id, stage=PipelineStage.DETECTION)

    store.save(checkpoint)
    loaded_before = store.load(project_id, PipelineStage.DETECTION)
    store.invalidate(project_id, PipelineStage.DETECTION)
    loaded_after = store.load(project_id, PipelineStage.DETECTION)

    assert loaded_before is not None
    assert loaded_before.status == CheckpointStatus.VALID
    assert loaded_after is not None
    assert loaded_after.status == CheckpointStatus.INVALIDATED


def test_clean_completed_removes_checkpoint_artifacts(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path)
    project_id = make_project_id()
    store.save(_make_checkpoint(project_id, stage=PipelineStage.CONCATENATION))
    store.save(_make_checkpoint(project_id, stage=PipelineStage.EXPORT, segment_index=0))

    cleaned = store.clean_completed(project_id)
    checkpoint_dir = tmp_path / "projects" / project_id / "checkpoints"

    assert cleaned == 2
    assert list(checkpoint_dir.glob("*.json")) == []


def test_checkpoint_file_naming_includes_segment_index(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path)
    project_id = make_project_id()
    checkpoint = _make_checkpoint(project_id, stage=PipelineStage.EXPORT, segment_index=7)

    store.save(checkpoint)

    expected = tmp_path / "projects" / project_id / "checkpoints" / "export_7.json"
    assert expected.exists()


def test_loading_nonexistent_checkpoint_returns_none(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path)

    assert store.load(make_project_id(), PipelineStage.AUDIO_SYNC) is None
