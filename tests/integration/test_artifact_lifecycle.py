"""Integration checks for artifact lifecycle and cleanup controls (T109)."""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime
from types import MethodType
from uuid import uuid4

import pytest

from cvcutter.application.checkpoint_manager import CheckpointManager
from cvcutter.application.pipeline import PipelineOrchestrator
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.services.types import DiskSpaceInfo
from cvcutter.infrastructure.logging.structured_logger import JsonFormatter
from cvcutter.infrastructure.persistence.json_checkpoint_store import JsonCheckpointStore
from cvcutter.infrastructure.persistence.json_project_store import JsonProjectStore
from cvcutter.presentation.viewmodels.settings_vm import SettingsViewModel
from cvcutter.shared.types import PipelineStage, ProcessingState

pytestmark = pytest.mark.integration


class _LocalVideoIO:
    def concatenate(self, video_paths, output_path, progress_callback=None):
        del video_paths
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\x01" * 8192)
        if progress_callback is not None:
            progress_callback(1, 1)
        return output_path

    def export_segment(
        self,
        *,
        source_path,
        output_path,
        start_seconds,
        end_seconds,
        audio_mix=None,
        quality="high",
        use_gpu=False,
        progress_callback=None,
    ):
        del source_path, start_seconds, end_seconds, audio_mix, quality, use_gpu
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\x02" * 4096)
        if progress_callback is not None:
            progress_callback(1, 1)
        return output_path

    def check_gpu_available(self):
        return False

    def get_disk_space(self, path):
        return DiskSpaceInfo(total_bytes=20_000_000, free_bytes=19_000_000, path=path)


class _SettingsWorkflowStub:
    def __init__(self) -> None:
        self.retention_policies: list[str] = []
        self.purged_projects: list[str] = []

    def load_config(self) -> ProjectConfig:
        return ProjectConfig()

    def save_config(self, config: ProjectConfig) -> None:
        del config

    def authenticate(self) -> bool:
        return True

    def test_connection(self) -> bool:
        return True

    def set_artifact_retention(self, policy: str) -> None:
        self.retention_policies.append(policy)

    def purge_artifacts(self, project_id: str) -> None:
        self.purged_projects.append(project_id)


@pytest.fixture
def artifact_context(tmp_path):
    now = datetime.now(UTC)
    source_path = tmp_path / "concert_source.mp4"
    source_path.write_bytes(b"\x00" * 50_000)
    project = ConcertProject(
        id=uuid4(),
        name="artifact_lifecycle_project",
        event_date=None,
        venue=None,
        source_videos=[
            SourceVideo(
                id=str(uuid4()),
                file_path=source_path,
                order_index=0,
                duration_seconds=180.0,
                resolution=(1920, 1080),
                codec="h264",
                creation_timestamp=now,
                file_hash="source-hash",
                file_size_bytes=source_path.stat().st_size,
            ),
        ],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=tmp_path / "exports",
        config_snapshot=ProjectConfig(),
        processing_state=ProcessingState.CREATED,
        created_at=now,
        updated_at=now,
    )

    app_data = tmp_path / "appdata"
    project_store = JsonProjectStore(app_data)
    checkpoint_store = JsonCheckpointStore(app_data)
    checkpoint_manager = CheckpointManager(checkpoint_store)
    project_store.save_project(project)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(f"tests.integration.artifact_lifecycle.{uuid4()}")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    orchestrator = PipelineOrchestrator(
        video_io=_LocalVideoIO(),
        checkpoint_manager=checkpoint_manager,
        project_store=project_store,
        logger=logger,
    )

    def _stub_detection(self, project_value, concatenated_path, progress_callback):
        del progress_callback
        segment = PerformanceSegment(
            id=uuid4(),
            segment_index=0,
            start_time_seconds=0.0,
            end_time_seconds=60.0,
            detection_confidence=0.9,
            effective_detection_mode="full",
            detection_signals=[],
        )
        self._project_store.save_segments(str(project_value.id), [segment])
        self._save_checkpoint(
            project=project_value,
            stage=PipelineStage.DETECTION,
            input_hashes=self._hash_for_concatenated_stage(concatenated_path),
            model_versions=self._model_versions(PipelineStage.DETECTION),
            output_references=["segments:1"],
        )
        return [segment]

    orchestrator._run_detection = MethodType(_stub_detection, orchestrator)

    def _read_records() -> list[dict[str, object]]:
        lines = [line for line in stream.getvalue().splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    yield project, orchestrator, app_data, _read_records

    handler.close()
    logger.handlers = []
    logger.propagate = True


def test_sc014_temporary_artifacts_are_cleaned_after_success(artifact_context) -> None:
    project, orchestrator, app_data, read_records = artifact_context

    orchestrator.run(project)

    concatenated_path = project.output_directory / f"{project.id}_concatenated.mp4"
    checkpoint_dir = app_data / "projects" / str(project.id) / "checkpoints"
    checkpoint_files = list(checkpoint_dir.glob("*.json")) if checkpoint_dir.exists() else []
    source_size = sum(item.file_size_bytes for item in project.source_videos)
    temporary_usage_bytes = (
        (concatenated_path.stat().st_size if concatenated_path.exists() else 0)
        + sum(path.stat().st_size for path in checkpoint_files)
    )
    exported_files = list(project.output_directory.glob("*segment_*.mp4"))
    cleanup_events = [item for item in read_records() if item.get("event") == "CLEANUP_COMPLETED"]

    assert not concatenated_path.exists()
    assert checkpoint_files == []
    assert temporary_usage_bytes < source_size * 0.1
    assert exported_files and all(path.exists() for path in exported_files)
    assert cleanup_events
    assert cleanup_events[-1]["decision"] == "auto-clean"


def test_user_retention_and_purge_controls_are_available() -> None:
    workflow = _SettingsWorkflowStub()
    view_model = SettingsViewModel(workflow=workflow, active_project_id="project-retention")

    view_model.set_artifact_retention("retain-user-selected")
    view_model.purge_artifacts("project-retention")

    assert workflow.retention_policies == ["retain-user-selected"]
    assert workflow.purged_projects == ["project-retention"]
    assert view_model.status_message == "成果物を削除しました。"
