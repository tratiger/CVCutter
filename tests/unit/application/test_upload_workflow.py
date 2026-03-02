"""Unit tests for quota-aware upload workflow behavior (T071)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from cvcutter.application.upload_workflow import UploadWorkflow
from cvcutter.domain.models.metadata import VideoMetadataMapping
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.models.upload import QuotaState, UploadRecord
from cvcutter.domain.services.types import UploadResult
from cvcutter.shared.types import (
    ExportStatus,
    MatchMethod,
    PipelineStage,
    PrivacySetting,
    ProcessingState,
    UploadStatus,
)

if TYPE_CHECKING:
    from pathlib import Path


class _MockUploadService:
    """Scripted upload service mock for workflow unit tests."""

    def __init__(
        self,
        scripted: dict[str, list[UploadResult]],
        *,
        fail_playlist_add: bool = False,
        fail_playlist_create: bool = False,
        auth_sequence: list[bool] | None = None,
    ) -> None:
        self._scripted = {title: list(results) for title, results in scripted.items()}
        self._fail_playlist_add = fail_playlist_add
        self._fail_playlist_create = fail_playlist_create
        self._auth_sequence = list(auth_sequence or [])
        self.calls: list[dict[str, object]] = []
        self.playlist_creates = 0

    def authenticate(self) -> bool:
        if self._auth_sequence:
            return self._auth_sequence.pop(0)
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
        self.calls.append(
            {
                "file_path": file_path,
                "title": metadata.title,
                "resumable_uri": resumable_uri,
                "bytes_uploaded": bytes_uploaded,
            },
        )
        scripted = self._scripted.get(metadata.title, [])
        result = scripted.pop(0) if scripted else _success_result(video_id=f"video-{metadata.title}")
        self._scripted[metadata.title] = scripted

        if session_callback is not None and result.resumable_uri:
            session_callback(result.resumable_uri)
        if progress_callback is not None:
            progress_callback(result.bytes_uploaded, max(result.bytes_uploaded, file_path.stat().st_size))
        return result

    def create_playlist(self, title: str, description: str = "", privacy=PrivacySetting.PUBLIC) -> str:
        del title, description, privacy
        if self._fail_playlist_create:
            raise RuntimeError("playlist create failure")
        self.playlist_creates += 1
        return "playlist-generated"

    def add_to_playlist(self, playlist_id: str, video_id: str) -> None:
        del playlist_id, video_id
        if self._fail_playlist_add:
            raise RuntimeError("playlist add failure")


class _MockQuotaStateStore:
    """In-memory quota-state store test double."""

    def __init__(self, state: QuotaState | None = None) -> None:
        self.state = state
        self.save_calls: list[QuotaState] = []

    def load(self) -> QuotaState | None:
        return self.state

    def save(self, state: QuotaState) -> None:
        self.state = state
        self.save_calls.append(state)


class _MockCheckpointManager:
    """Checkpoint manager stub capturing saved checkpoints."""

    def __init__(self) -> None:
        self.saved = []

    def save_checkpoint(self, checkpoint) -> None:
        self.saved.append(checkpoint)


class _MockProjectStore:
    """Project store stub for upload-workflow unit tests."""

    def __init__(
        self,
        *,
        project_id: str,
        segments: list[PerformanceSegment],
        mappings: list[VideoMetadataMapping],
        uploads: list[UploadRecord],
    ) -> None:
        self._project_id = project_id
        self._segments = segments
        self._mappings = mappings
        self._uploads = uploads
        self.save_upload_calls = 0

    def save_upload_records(self, project_id: str, uploads: list[UploadRecord]) -> None:
        assert project_id == self._project_id
        self._uploads = uploads
        self.save_upload_calls += 1

    def load_upload_records(self, project_id: str) -> list[UploadRecord]:
        assert project_id == self._project_id
        return self._uploads

    def load_segments(self, project_id: str) -> list[PerformanceSegment]:
        assert project_id == self._project_id
        return self._segments

    def load_mappings(self, project_id: str) -> list[VideoMetadataMapping]:
        assert project_id == self._project_id
        return self._mappings


def _make_project(tmp_path: Path) -> ConcertProject:
    now = datetime.now(UTC)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    source_video = SourceVideo(
        id=str(uuid4()),
        file_path=source,
        order_index=0,
        duration_seconds=180.0,
        resolution=(1920, 1080),
        codec="h264",
        creation_timestamp=now,
        file_hash="source-hash",
        file_size_bytes=source.stat().st_size,
    )
    return ConcertProject(
        id=uuid4(),
        name="Upload Workflow Unit",
        event_date=None,
        venue="hall",
        source_videos=[source_video],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=tmp_path / "output",
        config_snapshot=ProjectConfig(),
        processing_state=ProcessingState.READY_FOR_UPLOAD,
        created_at=now,
        updated_at=now,
    )


def _make_segment(tmp_path: Path, segment_index: int) -> PerformanceSegment:
    exported = tmp_path / f"segment-{segment_index:03d}.mp4"
    exported.write_bytes(b"x" * 1024)
    return PerformanceSegment(
        id=uuid4(),
        segment_index=segment_index,
        start_time_seconds=float(segment_index * 60),
        end_time_seconds=float(segment_index * 60 + 45),
        detection_confidence=0.9,
        effective_detection_mode="full",
        detection_signals=[],
        fallback_reason=None,
        exported_file_path=exported,
        export_status=ExportStatus.EXPORTED,
        user_adjusted=False,
    )


def _make_mapping(segment: PerformanceSegment, title: str) -> VideoMetadataMapping:
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


def _make_record(segment: PerformanceSegment, mapping: VideoMetadataMapping, status: UploadStatus) -> UploadRecord:
    error_detail = "failed" if status == UploadStatus.FAILED else None
    return UploadRecord(
        id=str(uuid4()),
        segment_id=str(segment.id),
        mapping_id=str(mapping.id),
        upload_status=status,
        privacy_setting=PrivacySetting.PUBLIC,
        error_detail=error_detail,
    )


def _success_result(video_id: str, *, bytes_uploaded: int = 1024) -> UploadResult:
    return UploadResult(
        success=True,
        video_id=video_id,
        resumable_uri="session://ok",
        bytes_uploaded=bytes_uploaded,
        failure_kind=None,
        resume_allowed=False,
        restart_from_zero=False,
        session_invalidated_at_utc=None,
        error_message=None,
    )


def _failure_result(
    *,
    failure_kind: str,
    resume_allowed: bool,
    restart_from_zero: bool,
    bytes_uploaded: int = 0,
) -> UploadResult:
    return UploadResult(
        success=False,
        video_id=None,
        resumable_uri="session://partial" if resume_allowed else None,
        bytes_uploaded=bytes_uploaded,
        failure_kind=failure_kind,
        resume_allowed=resume_allowed,
        restart_from_zero=restart_from_zero,
        session_invalidated_at_utc=datetime.now(UTC) if failure_kind == "SESSION_INVALIDATED" else None,
        error_message=failure_kind,
    )


def test_upload_state_transitions_and_per_upload_checkpoint_writes(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segments = [_make_segment(tmp_path, 0), _make_segment(tmp_path, 1)]
    mappings = [_make_mapping(segments[0], "title-success"), _make_mapping(segments[1], "title-failure")]
    records = [
        _make_record(segments[0], mappings[0], UploadStatus.PENDING),
        _make_record(segments[1], mappings[1], UploadStatus.PENDING),
    ]
    upload_service = _MockUploadService(
        {
            "title-success": [_success_result("video-success")],
            "title-failure": [
                _failure_result(
                    failure_kind="UNKNOWN",
                    resume_allowed=False,
                    restart_from_zero=False,
                ),
            ],
        },
    )
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=segments,
        mappings=mappings,
        uploads=records,
    )
    checkpoint_manager = _MockCheckpointManager()
    workflow = UploadWorkflow(upload_service, quota_store, project_store, checkpoint_manager)

    workflow.start_upload(project, records)

    assert records[0].upload_status == UploadStatus.COMPLETED
    assert records[1].upload_status == UploadStatus.FAILED
    assert records[0].youtube_url == "https://www.youtube.com/watch?v=video-success"
    assert len(checkpoint_manager.saved) >= 2
    assert all(checkpoint.stage == PipelineStage.UPLOAD for checkpoint in checkpoint_manager.saved)


def test_quota_exhaustion_queues_remaining_uploads_and_auto_resume_after_reset(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segments = [_make_segment(tmp_path, 0), _make_segment(tmp_path, 1)]
    mappings = [_make_mapping(segments[0], "title-a"), _make_mapping(segments[1], "title-b")]
    records = [
        _make_record(segments[0], mappings[0], UploadStatus.PENDING),
        _make_record(segments[1], mappings[1], UploadStatus.PENDING),
    ]
    upload_service = _MockUploadService(
        {
            "title-a": [_success_result("video-a")],
            "title-b": [_success_result("video-b")],
        },
    )
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=8_400,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=segments,
        mappings=mappings,
        uploads=records,
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())

    first_pass = workflow.start_upload(project, records)

    assert first_pass[0].upload_status == UploadStatus.COMPLETED
    assert first_pass[1].upload_status == UploadStatus.QUEUED
    assert len(upload_service.calls) == 1

    resumed = workflow.run_quota_reset_scheduler(
        project,
        records,
        now_utc=datetime.now(UTC) + timedelta(days=1),
    )

    assert resumed[1].upload_status == UploadStatus.COMPLETED
    assert len(upload_service.calls) == 2


def test_retry_failed_uses_resume_or_restart_from_zero_policy(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segment_resume = _make_segment(tmp_path, 0)
    segment_restart = _make_segment(tmp_path, 1)
    mapping_resume = _make_mapping(segment_resume, "title-resume")
    mapping_restart = _make_mapping(segment_restart, "title-restart")
    record_resume = _make_record(segment_resume, mapping_resume, UploadStatus.FAILED)
    record_resume.failure_kind = "NETWORK_TRANSIENT"
    record_resume.error_detail = "network"
    record_resume.resumable_upload_uri = "session://resume"
    record_resume.bytes_uploaded = 512
    record_resume.retry_count = 2

    record_restart = _make_record(segment_restart, mapping_restart, UploadStatus.FAILED)
    record_restart.failure_kind = "SESSION_INVALIDATED"
    record_restart.error_detail = "stale-session"
    record_restart.session_invalidated_at_utc = datetime.now(UTC)
    record_restart.restart_from_zero = True
    record_restart.resumable_upload_uri = "session://stale"
    record_restart.bytes_uploaded = 768
    record_restart.retry_count = 1

    upload_service = _MockUploadService(
        {
            "title-resume": [_success_result("video-resume", bytes_uploaded=1024)],
            "title-restart": [_success_result("video-restart", bytes_uploaded=1024)],
        },
    )
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=[segment_resume, segment_restart],
        mappings=[mapping_resume, mapping_restart],
        uploads=[record_resume, record_restart],
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())
    workflow.start_upload(project, [record_resume, record_restart])

    updated_resume = workflow.retry_failed(record_resume.id)
    updated_restart = workflow.retry_failed(record_restart.id)

    resume_call = next(call for call in upload_service.calls if call["title"] == "title-resume")
    restart_call = next(call for call in upload_service.calls if call["title"] == "title-restart")

    assert resume_call["resumable_uri"] == "session://resume"
    assert resume_call["bytes_uploaded"] == 512
    assert restart_call["resumable_uri"] is None
    assert restart_call["bytes_uploaded"] == 0
    assert updated_resume.upload_status == UploadStatus.COMPLETED
    assert updated_restart.upload_status == UploadStatus.COMPLETED
    assert updated_resume.retry_count == 0
    assert updated_restart.retry_count == 0


def test_orphaned_uploading_records_are_recovered_to_failed_on_start(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segment = _make_segment(tmp_path, 0)
    mapping = _make_mapping(segment, "title-orphan")
    orphan = _make_record(segment, mapping, UploadStatus.UPLOADING)
    upload_service = _MockUploadService({"title-orphan": [_success_result("video-orphan")]})
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=[segment],
        mappings=[mapping],
        uploads=[orphan],
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())

    result = workflow.start_upload(project, [orphan])

    assert result[0].upload_status == UploadStatus.FAILED
    assert "interrupted" in (result[0].error_detail or "").lower()


def test_startup_resume_recovers_orphaned_uploading_without_queued_records(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segment = _make_segment(tmp_path, 0)
    mapping = _make_mapping(segment, "title-startup-orphan")
    orphan = _make_record(segment, mapping, UploadStatus.UPLOADING)
    upload_service = _MockUploadService({"title-startup-orphan": [_success_result("video-unused")]})
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=[segment],
        mappings=[mapping],
        uploads=[orphan],
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())

    resumed = workflow.resume_queued_on_startup(project)

    assert resumed[0].upload_status == UploadStatus.FAILED
    assert "interrupted" in (resumed[0].error_detail or "").lower()


def test_playlist_assignment_failure_does_not_block_completed_state(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segment = _make_segment(tmp_path, 0)
    mapping = _make_mapping(segment, "title-playlist-fail")
    record = _make_record(segment, mapping, UploadStatus.PENDING)
    record.playlist_id = "playlist-fixed"
    upload_service = _MockUploadService(
        {"title-playlist-fail": [_success_result("video-playlist-fail")]},
        fail_playlist_add=True,
    )
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=[segment],
        mappings=[mapping],
        uploads=[record],
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())

    result = workflow.start_upload(project, [record])

    assert result[0].upload_status == UploadStatus.COMPLETED


def test_resume_queued_on_startup_sets_retry_context_for_failed_records(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segment = _make_segment(tmp_path, 0)
    mapping = _make_mapping(segment, "title-retry-after-startup")
    failed_record = _make_record(segment, mapping, UploadStatus.FAILED)
    failed_record.error_detail = "network"
    failed_record.failure_kind = "NETWORK_TRANSIENT"
    failed_record.resumable_upload_uri = "session://resume"
    failed_record.bytes_uploaded = 256
    upload_service = _MockUploadService(
        {"title-retry-after-startup": [_success_result("video-retry-after-startup")]},
    )
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=[segment],
        mappings=[mapping],
        uploads=[failed_record],
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())

    workflow.resume_queued_on_startup(project)
    updated = workflow.retry_failed(failed_record.id)

    assert updated.upload_status == UploadStatus.COMPLETED


def test_playlist_creation_failure_does_not_crash_upload_run(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segment = _make_segment(tmp_path, 0)
    mapping = _make_mapping(segment, "title-playlist-create-fail")
    record = _make_record(segment, mapping, UploadStatus.PENDING)
    upload_service = _MockUploadService(
        {"title-playlist-create-fail": [_success_result("video-playlist-create-fail")]},
        fail_playlist_create=True,
    )
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=[segment],
        mappings=[mapping],
        uploads=[record],
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())

    result = workflow.start_upload(project, [record])

    assert result[0].upload_status == UploadStatus.COMPLETED
    assert "playlist_creation_failed" in (result[0].error_detail or "")


def test_retry_failed_with_project_ignores_stale_cached_records(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segment = _make_segment(tmp_path, 0)
    mapping = _make_mapping(segment, "title-retry-stale-cache")
    failed_record = _make_record(segment, mapping, UploadStatus.FAILED)
    failed_record.error_detail = "network"
    failed_record.failure_kind = "NETWORK_TRANSIENT"
    upload_service = _MockUploadService(
        {"title-retry-stale-cache": [_success_result("video-retry-stale-cache")]},
    )
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=[segment],
        mappings=[mapping],
        uploads=[failed_record],
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())
    workflow._cached_records = [
        _make_record(segment, mapping, UploadStatus.PENDING),
    ]

    updated = workflow.retry_failed(failed_record.id, project=project)

    assert updated.upload_status == UploadStatus.COMPLETED


def test_quota_queue_clears_restart_from_zero_flags(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segment = _make_segment(tmp_path, 0)
    mapping = _make_mapping(segment, "title-queue-reset-flags")
    failed_record = _make_record(segment, mapping, UploadStatus.FAILED)
    failed_record.error_detail = "session invalidated"
    failed_record.failure_kind = "SESSION_INVALIDATED"
    failed_record.session_invalidated_at_utc = datetime.now(UTC)
    failed_record.restart_from_zero = True
    failed_record.bytes_uploaded = 512
    failed_record.resumable_upload_uri = "session://stale"
    upload_service = _MockUploadService({"title-queue-reset-flags": [_success_result("video-unused")]})
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=9_600,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=[segment],
        mappings=[mapping],
        uploads=[failed_record],
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())
    workflow.start_upload(project, [failed_record])

    queued = workflow.retry_failed(failed_record.id)

    assert queued.upload_status == UploadStatus.QUEUED
    assert queued.restart_from_zero is False
    assert queued.session_invalidated_at_utc is None


def test_auth_failure_queued_records_resume_after_auth_recovers(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segments = [_make_segment(tmp_path, 0), _make_segment(tmp_path, 1)]
    mappings = [_make_mapping(segments[0], "title-auth-a"), _make_mapping(segments[1], "title-auth-b")]
    records = [
        _make_record(segments[0], mappings[0], UploadStatus.PENDING),
        _make_record(segments[1], mappings[1], UploadStatus.PENDING),
    ]
    upload_service = _MockUploadService(
        {
            "title-auth-a": [_success_result("video-auth-a")],
            "title-auth-b": [_success_result("video-auth-b")],
        },
        auth_sequence=[False, True],
    )
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=segments,
        mappings=mappings,
        uploads=records,
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())

    first_pass = workflow.start_upload(project, records)
    first_statuses = [record.upload_status for record in first_pass]
    second_pass = workflow.start_upload(project, records)

    assert first_statuses == [UploadStatus.QUEUED, UploadStatus.QUEUED]
    assert all(record.upload_status == UploadStatus.COMPLETED for record in second_pass)
    assert len(upload_service.calls) == 2


def test_quota_exhausted_response_short_circuits_remaining_api_calls(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    segments = [_make_segment(tmp_path, 0), _make_segment(tmp_path, 1)]
    mappings = [_make_mapping(segments[0], "title-quota-a"), _make_mapping(segments[1], "title-quota-b")]
    records = [
        _make_record(segments[0], mappings[0], UploadStatus.PENDING),
        _make_record(segments[1], mappings[1], UploadStatus.PENDING),
    ]
    upload_service = _MockUploadService(
        {
            "title-quota-a": [
                _failure_result(
                    failure_kind="QUOTA_EXHAUSTED",
                    resume_allowed=True,
                    restart_from_zero=False,
                ),
            ],
            "title-quota-b": [_success_result("video-quota-b")],
        },
    )
    quota_store = _MockQuotaStateStore(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=1),
            last_updated=datetime.now(UTC),
        ),
    )
    project_store = _MockProjectStore(
        project_id=str(project.id),
        segments=segments,
        mappings=mappings,
        uploads=records,
    )
    workflow = UploadWorkflow(upload_service, quota_store, project_store, _MockCheckpointManager())

    result = workflow.start_upload(project, records)

    assert result[0].upload_status == UploadStatus.QUEUED
    assert result[1].upload_status == UploadStatus.QUEUED
    assert len(upload_service.calls) == 1
    assert quota_store.state is not None
    assert quota_store.state.daily_used == quota_store.state.daily_limit
