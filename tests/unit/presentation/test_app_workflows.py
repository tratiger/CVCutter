"""Unit tests for presentation app workflow adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.infrastructure.persistence.json_config import JsonConfig
from cvcutter.infrastructure.persistence.json_project_store import JsonProjectStore
from cvcutter.presentation import app as app_module
from cvcutter.shared.hashing import compute_file_hash
from cvcutter.shared.types import ExportStatus, ProcessingState


@dataclass
class _ProbeResult:
    duration_seconds: float = 120.0
    resolution: tuple[int, int] = (1920, 1080)
    codec: str = "h264"
    file_size_bytes: int = 4096


class _FakeVideoProber:
    def probe(self, file_path) -> _ProbeResult:
        del file_path
        return _ProbeResult()


class _FakePipeline:
    def __init__(self) -> None:
        self.run_calls: list[str] = []
        self.resume_calls: list[str] = []
        self.restart_calls: list[str] = []
        self.pause_calls = 0
        self.cancel_calls = 0

    def run(self, project: ConcertProject, progress_callback) -> ConcertProject:
        del progress_callback
        self.run_calls.append(str(project.id))
        return project

    def resume(self, project: ConcertProject, progress_callback) -> ConcertProject:
        del progress_callback
        self.resume_calls.append(str(project.id))
        return project

    def restart(self, project: ConcertProject, progress_callback) -> ConcertProject:
        del progress_callback
        self.restart_calls.append(str(project.id))
        return project

    def pause(self) -> None:
        self.pause_calls += 1

    def cancel(self) -> None:
        self.cancel_calls += 1


def test_load_workflow_creates_and_persists_project(tmp_path) -> None:
    state = app_module._AppState()
    project_store = JsonProjectStore(tmp_path)
    config_store = JsonConfig(tmp_path)
    load_workflow = app_module._LoadWorkflowService(
        state,
        project_store=project_store,
        video_io=_FakeVideoProber(),
        config_store=config_store,
    )
    video_path = tmp_path / "input.mts"
    video_path.write_bytes(b"video")

    payload = load_workflow.create_project(
        project_name="Concert A",
        video_files=[video_path],
        external_audio_file=None,
        program_pdf_file=None,
        form_csv_file=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=tmp_path / "output",
    )

    assert payload["project_id"] == state.project_id
    saved = project_store.load_project(state.project_id)
    assert saved is not None
    assert saved.name == "Concert A"
    assert saved.source_videos[0].file_path == video_path.resolve()


def test_processing_workflow_delegates_pipeline_and_returns_segments(tmp_path) -> None:
    project_store = JsonProjectStore(tmp_path)
    source_path = tmp_path / "input.mts"
    source_path.write_bytes(b"video")
    now_utc = datetime.now(UTC)
    project = ConcertProject(
        id=uuid4(),
        name="Concert B",
        event_date=None,
        venue=None,
        source_videos=[
            SourceVideo(
                id=str(uuid4()),
                file_path=source_path.resolve(),
                order_index=0,
                duration_seconds=60.0,
                resolution=(1920, 1080),
                codec="h264",
                creation_timestamp=now_utc,
                file_hash=compute_file_hash(source_path),
                file_size_bytes=source_path.stat().st_size,
            ),
        ],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=tmp_path / "output",
        config_snapshot=ProjectConfig(),
        processing_state=ProcessingState.CREATED,
        created_at=now_utc,
        updated_at=now_utc,
    )
    project_store.save_project(project)
    segment = PerformanceSegment(
        id=uuid4(),
        segment_index=0,
        start_time_seconds=0.0,
        end_time_seconds=10.0,
        detection_confidence=0.9,
        effective_detection_mode="full",
        detection_signals=[],
        fallback_reason=None,
        exported_file_path=None,
        export_status=ExportStatus.NOT_EXPORTED,
        user_adjusted=False,
    )
    project_store.save_segments(str(project.id), [segment])

    pipeline = _FakePipeline()
    process_workflow = app_module._ProcessingWorkflowService(
        project_store=project_store,
        pipeline=pipeline,
    )

    result = process_workflow.start(str(project.id), lambda _: None)

    assert len(result) == 1
    assert pipeline.restart_calls == [str(project.id)]
    process_workflow.pause()
    process_workflow.cancel()
    assert pipeline.pause_calls == 1
    assert pipeline.cancel_calls == 1
