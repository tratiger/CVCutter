"""Integration scaffolds for upload-with-quota workflow (T072)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from cvcutter.application.upload_workflow import UploadWorkflow
from cvcutter.domain.models.metadata import VideoMetadataMapping
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.models.upload import QuotaState, UploadRecord
from cvcutter.domain.services.types import UploadResult
from cvcutter.infrastructure.persistence.json_project_store import JsonProjectStore
from cvcutter.infrastructure.persistence.json_quota_state_store import JsonQuotaStateStore
from cvcutter.presentation.viewmodels.upload_vm import UploadViewModel
from cvcutter.shared.types import (
    ExportStatus,
    MatchMethod,
    PrivacySetting,
    ProcessingState,
    UploadStatus,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


class _CheckpointManagerStub:
    """Checkpoint manager stub for integration scaffolds."""

    def __init__(self) -> None:
        self.saved = []

    def save_checkpoint(self, checkpoint) -> None:
        self.saved.append(checkpoint)


class _UploadServiceStub:
    """Deterministic upload service stub for integration workflows."""

    def __init__(self) -> None:
        self.calls = 0

    def authenticate(self) -> bool:
        return True

    def upload(
        self,
        file_path: Path,
        metadata,
        progress_callback=None,
        resumable_uri: str | None = None,
        bytes_uploaded: int = 0,
        session_callback=None,
    ) -> UploadResult:
        del resumable_uri, bytes_uploaded
        self.calls += 1
        if session_callback is not None:
            session_callback(f"session://{metadata.title}")
        if progress_callback is not None:
            progress_callback(file_path.stat().st_size, file_path.stat().st_size)
        return UploadResult(
            success=True,
            video_id=f"video-{self.calls}",
            resumable_uri=f"session://{metadata.title}",
            bytes_uploaded=file_path.stat().st_size,
            failure_kind=None,
            resume_allowed=False,
            restart_from_zero=False,
            session_invalidated_at_utc=None,
            error_message=None,
        )

    def create_playlist(self, title: str, description: str = "", privacy=PrivacySetting.PUBLIC) -> str:
        del title, description, privacy
        return "playlist-integration"

    def add_to_playlist(self, playlist_id: str, video_id: str) -> None:
        del playlist_id, video_id


class _UploadVmWorkflowAdapter:
    """Small adapter exposing UploadWorkflow protocol expected by UploadViewModel."""

    def __init__(self, records: list[UploadRecord], quota_state: QuotaState) -> None:
        self._records = records
        self._quota_state = quota_state

    def start_upload(self, project_id: str) -> list[UploadRecord]:
        del project_id
        return self._records

    def pause_upload(self) -> None:
        return

    def retry_failed(self, upload_record_id: str) -> UploadRecord:
        return next(record for record in self._records if record.id == upload_record_id)

    def quota_state(self) -> QuotaState:
        return self._quota_state


def _create_project(base_dir: Path) -> ConcertProject:
    now = datetime.now(UTC)
    source_path = base_dir / "source.mp4"
    source_path.write_bytes(b"source")
    source = SourceVideo(
        id=str(uuid4()),
        file_path=source_path,
        order_index=0,
        duration_seconds=180.0,
        resolution=(1920, 1080),
        codec="h264",
        creation_timestamp=now,
        file_hash="source-hash",
        file_size_bytes=source_path.stat().st_size,
    )
    return ConcertProject(
        id=uuid4(),
        name="Integration Upload Project",
        event_date=None,
        venue="hall",
        source_videos=[source],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=base_dir / "output",
        config_snapshot=ProjectConfig(),
        processing_state=ProcessingState.READY_FOR_UPLOAD,
        created_at=now,
        updated_at=now,
    )


def _create_segment(base_dir: Path, index: int) -> PerformanceSegment:
    exported = base_dir / f"segment-{index}.mp4"
    exported.write_bytes(b"x" * 1024)
    return PerformanceSegment(
        id=uuid4(),
        segment_index=index,
        start_time_seconds=float(index * 60),
        end_time_seconds=float(index * 60 + 45),
        detection_confidence=0.9,
        effective_detection_mode="full",
        detection_signals=[],
        fallback_reason=None,
        exported_file_path=exported,
        export_status=ExportStatus.EXPORTED,
        user_adjusted=False,
    )


def _create_mapping(segment: PerformanceSegment, title: str) -> VideoMetadataMapping:
    return VideoMetadataMapping(
        id=uuid4(),
        segment_id=str(segment.id),
        program_entry_id=None,
        form_response_id=None,
        match_confidence=1.0,
        match_method=MatchMethod.MANUAL,
        match_signals=[],
        user_verified=True,
        final_title=title,
        final_description=f"{title} description",
        final_privacy=PrivacySetting.PUBLIC,
        final_category_id="10",
        final_tags=["concert"],
    )


def _create_upload_record(segment: PerformanceSegment, mapping: VideoMetadataMapping) -> UploadRecord:
    return UploadRecord(
        id=str(uuid4()),
        segment_id=str(segment.id),
        mapping_id=str(mapping.id),
        upload_status=UploadStatus.PENDING,
        privacy_setting=PrivacySetting.PUBLIC,
    )


def _seed_project_state(
    store: JsonProjectStore,
    project: ConcertProject,
    segments: list[PerformanceSegment],
    mappings: list[VideoMetadataMapping],
    uploads: list[UploadRecord],
) -> None:
    project_id = str(project.id)
    store.save_project(project)
    store.save_segments(project_id, segments)
    store.save_mappings(project_id, mappings)
    store.save_upload_records(project_id, uploads)


def test_upload_with_quota_integration_scaffold(tmp_path: Path) -> None:
    project_store = JsonProjectStore(tmp_path)
    quota_store = JsonQuotaStateStore(tmp_path)
    project = _create_project(tmp_path)
    segments = [_create_segment(tmp_path, 0)]
    mappings = [_create_mapping(segments[0], "title-1")]
    uploads = [_create_upload_record(segments[0], mappings[0])]
    _seed_project_state(project_store, project, segments, mappings, uploads)
    quota_store.save(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )

    workflow = UploadWorkflow(
        upload_service=_UploadServiceStub(),
        quota_state_store=quota_store,
        project_store=project_store,
        checkpoint_manager=_CheckpointManagerStub(),
    )
    result = workflow.start_upload(project, uploads)

    assert len(result) == 1
    assert result[0].upload_status == UploadStatus.COMPLETED


def test_fr051_quota_queueing_and_fr054_status_url_display(tmp_path: Path) -> None:
    project_store = JsonProjectStore(tmp_path)
    quota_store = JsonQuotaStateStore(tmp_path)
    project = _create_project(tmp_path)
    segments = [_create_segment(tmp_path, 0), _create_segment(tmp_path, 1)]
    mappings = [_create_mapping(segments[0], "title-a"), _create_mapping(segments[1], "title-b")]
    uploads = [
        _create_upload_record(segments[0], mappings[0]),
        _create_upload_record(segments[1], mappings[1]),
    ]
    _seed_project_state(project_store, project, segments, mappings, uploads)
    quota_store.save(
        QuotaState(
            daily_limit=10_000,
            daily_used=8_400,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )

    workflow = UploadWorkflow(
        upload_service=_UploadServiceStub(),
        quota_state_store=quota_store,
        project_store=project_store,
        checkpoint_manager=_CheckpointManagerStub(),
    )
    result = workflow.start_upload(project, uploads)
    view_model = UploadViewModel(
        workflow=_UploadVmWorkflowAdapter(result, workflow.quota_state()),
        project_id=str(project.id),
    )
    view_model.start_upload()

    assert result[0].upload_status == UploadStatus.COMPLETED
    assert result[1].upload_status == UploadStatus.QUEUED
    assert result[0].youtube_url is not None
    assert result[0].id in view_model.per_video_urls


def test_fr055_next_launch_auto_resume_for_queued_uploads(tmp_path: Path) -> None:
    project_store = JsonProjectStore(tmp_path)
    quota_store = JsonQuotaStateStore(tmp_path)
    project = _create_project(tmp_path)
    segments = [_create_segment(tmp_path, 0), _create_segment(tmp_path, 1)]
    mappings = [_create_mapping(segments[0], "title-a"), _create_mapping(segments[1], "title-b")]
    uploads = [
        _create_upload_record(segments[0], mappings[0]),
        _create_upload_record(segments[1], mappings[1]),
    ]
    _seed_project_state(project_store, project, segments, mappings, uploads)
    quota_store.save(
        QuotaState(
            daily_limit=10_000,
            daily_used=8_400,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )

    first_launch = UploadWorkflow(
        upload_service=_UploadServiceStub(),
        quota_state_store=quota_store,
        project_store=project_store,
        checkpoint_manager=_CheckpointManagerStub(),
    )
    first_launch.start_upload(project, uploads)

    quota_store.save(
        QuotaState(
            daily_limit=10_000,
            daily_used=10_000,
            reset_timestamp_utc=datetime.now(UTC) - timedelta(minutes=1),
            last_updated=datetime.now(UTC),
        ),
    )
    second_launch = UploadWorkflow(
        upload_service=_UploadServiceStub(),
        quota_state_store=quota_store,
        project_store=project_store,
        checkpoint_manager=_CheckpointManagerStub(),
    )
    resumed = second_launch.resume_queued_on_startup(project)
    statuses = {record.upload_status for record in resumed}

    assert statuses == {UploadStatus.COMPLETED}
    persisted = project_store.load_upload_records(str(project.id))
    assert all(record.youtube_url for record in persisted)


@pytest.mark.benchmark
def test_sc011_benchmark_scaffold() -> None:
    benchmark_run_id = UUID("00000000-0000-0000-0000-000000000011")
    pytest.skip(
        f"SC-011 benchmark scaffold for run {benchmark_run_id}: "
        "validate <2h for 6 upload-ready segments under defined network profile.",
    )
