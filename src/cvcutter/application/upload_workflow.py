"""Quota-aware upload workflow orchestration."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING
from uuid import uuid4

from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.domain.models.upload import QuotaState
from cvcutter.domain.services.types import UploadMetadata
from cvcutter.shared.time_utils import pt_midnight_utc
from cvcutter.shared.types import CheckpointStatus, PipelineStage, PrivacySetting, UploadStatus

if TYPE_CHECKING:
    from cvcutter.application.checkpoint_manager import CheckpointManager
    from cvcutter.domain.models.metadata import VideoMetadataMapping
    from cvcutter.domain.models.project import ConcertProject
    from cvcutter.domain.models.segment import PerformanceSegment
    from cvcutter.domain.models.upload import UploadRecord
    from cvcutter.domain.services.project_store import ProjectStore
    from cvcutter.domain.services.quota_state_store import QuotaStateStore
    from cvcutter.domain.services.upload_service import UploadService


class UploadWorkflow:
    """Coordinate upload queue processing with quota and checkpoint persistence."""

    _run_lock = RLock()
    _is_upload_run_active = False
    _active_upload_owner: UploadWorkflow | None = None

    def __init__(
        self,
        upload_service: UploadService,
        quota_state_store: QuotaStateStore,
        project_store: ProjectStore,
        checkpoint_manager: CheckpointManager,
        *,
        max_retries: int = 5,
    ) -> None:
        self._upload_service = upload_service
        self._quota_state_store = quota_state_store
        self._project_store = project_store
        self._checkpoint_manager = checkpoint_manager
        self._max_retries = max(0, max_retries)

        self._pause_requested = False
        self._cancel_requested = False
        self._active_project: ConcertProject | None = None
        self._cached_records: list[UploadRecord] = []
        self._quota_state_cache: QuotaState | None = None

    def start_upload(
        self,
        project: ConcertProject,
        records: list[UploadRecord] | None = None,
    ) -> list[UploadRecord]:
        """Start or continue processing upload records with quota-aware queue behavior."""
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("Upload workflow is already running.")
        upload_run_activated = False
        try:
            if self.__class__._is_upload_run_active:
                raise RuntimeError("Upload workflow is already running.")
            self.__class__._is_upload_run_active = True
            self.__class__._active_upload_owner = self
            upload_run_activated = True
            self._pause_requested = False
            self._cancel_requested = False
            project_id = self._project_id(project)
            active_records = self._load_records(project_id, records)
            self._active_project = project
            self._cached_records = active_records

            quota_state, reset_applied = self._reset_quota_if_due(self._load_quota_state())
            if reset_applied:
                self._release_queued_records_after_reset(active_records)
            self._recover_orphaned_uploads(project, active_records)
            self._persist_state(project_id, active_records, quota_state)

            if not self._upload_service.authenticate():
                self._queue_pending_for_auth_retry(active_records, project, quota_state)
                return active_records

            self._release_auth_queued_records(active_records)
            segments = self._segments_by_id(project_id)
            mappings = self._mappings_by_id(project_id)
            self._assign_playlist_if_needed(project, active_records)

            for record in self._sorted_records(active_records, segments):
                if self._cancel_requested or self._pause_requested:
                    break

                if record.upload_status == UploadStatus.COMPLETED:
                    continue
                if record.upload_status == UploadStatus.QUEUED:
                    continue
                if record.upload_status == UploadStatus.FAILED:
                    continue
                if record.upload_status != UploadStatus.PENDING:
                    continue

                quota_state, reset_applied = self._reset_quota_if_due(quota_state)
                if reset_applied:
                    self._release_queued_records_after_reset(active_records)
                if not quota_state.can_upload(record.quota_cost):
                    self._queue_record(record, "Daily quota exhausted; queued until reset.")
                    self._write_upload_checkpoint(project, record)
                    self._persist_state(project_id, active_records, quota_state)
                    continue

                quota_state = self._process_one_record(
                    project=project,
                    record=record,
                    segments=segments,
                    mappings=mappings,
                    quota_state=quota_state,
                    all_records=active_records,
                )
                self._persist_state(project_id, active_records, quota_state)

            self._persist_state(project_id, active_records, quota_state)
            return active_records
        finally:
            if upload_run_activated:
                self.__class__._is_upload_run_active = False
                if self.__class__._active_upload_owner is self:
                    self.__class__._active_upload_owner = None
            self._pause_requested = False
            self._cancel_requested = False
            self._run_lock.release()

    def retry_failed(self, record_id: str, project: ConcertProject | None = None) -> UploadRecord:
        """Retry one failed upload and decide resume-vs-restart-from-zero semantics."""
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("Upload workflow is already running.")
        try:
            if project is not None:
                self._active_project = project
                self._cached_records = self._project_store.load_upload_records(self._project_id(project))
            if self._active_project is None:
                raise RuntimeError("No active project context for retry.")

            project = self._active_project
            project_id = self._project_id(project)
            records = self._cached_records or self._project_store.load_upload_records(project_id)
            target = next((record for record in records if record.id == record_id), None)
            if target is None:
                raise ValueError(f"Unknown upload record: {record_id}")
            if target.upload_status == UploadStatus.UPLOADING:
                self._mark_failed(
                    target,
                    failure_kind="UNKNOWN",
                    error_message="Upload interrupted by previous session.",
                    restart_from_zero=False,
                    session_invalidated_at_utc=None,
                )
            if target.upload_status != UploadStatus.FAILED:
                return target

            prior_failure_kind = target.failure_kind
            target.transition_to(UploadStatus.PENDING)
            target.error_detail = None
            target.failure_kind = None
            target.restart_from_zero = False
            target.session_invalidated_at_utc = None
            if prior_failure_kind == "SESSION_INVALIDATED":
                target.resumable_upload_uri = None
                target.bytes_uploaded = 0

            quota_state, reset_applied = self._reset_quota_if_due(self._load_quota_state())
            if reset_applied:
                self._release_queued_records_after_reset(records)
            if not quota_state.can_upload(target.quota_cost):
                self._queue_record(target, "Daily quota exhausted; queued until reset.")
                self._write_upload_checkpoint(project, target)
                self._persist_state(project_id, records, quota_state)
                return target

            if not self._upload_service.authenticate():
                target.transition_to(UploadStatus.UPLOADING)
                self._mark_failed(
                    target,
                    failure_kind="AUTH_FAILURE",
                    error_message="Authentication failed.",
                    restart_from_zero=False,
                    session_invalidated_at_utc=None,
                )
                self._write_upload_checkpoint(project, target)
                self._persist_state(project_id, records, quota_state)
                return target

            updated_quota = self._process_one_record(
                project=project,
                record=target,
                segments=self._segments_by_id(project_id),
                mappings=self._mappings_by_id(project_id),
                quota_state=quota_state,
                all_records=records,
            )
            self._persist_state(project_id, records, updated_quota)
            return target
        finally:
            self._run_lock.release()

    def pause(self) -> None:
        """Request queue pause at the next record boundary."""
        owner = self.__class__._active_upload_owner
        if owner is None:
            return
        owner._pause_requested = True

    def cancel(self) -> None:
        """Request queue cancellation at the next record boundary."""
        owner = self.__class__._active_upload_owner
        if owner is None:
            return
        owner._cancel_requested = True

    def pause_upload(self) -> None:
        """Compatibility alias for presentation-layer protocol."""
        self.pause()

    def quota_state(self) -> QuotaState:
        """Return latest quota state snapshot."""
        if self._quota_state_cache is not None:
            return self._quota_state_cache
        self._quota_state_cache = self._load_quota_state()
        return self._quota_state_cache

    def run_quota_reset_scheduler(
        self,
        project: ConcertProject,
        records: list[UploadRecord] | None = None,
        *,
        now_utc: datetime | None = None,
    ) -> list[UploadRecord]:
        """Auto-resume queued records once quota reset time is reached."""
        project_id = self._project_id(project)
        if not self._run_lock.acquire(blocking=False):
            return self._project_store.load_upload_records(project_id)
        try:
            if self.__class__._is_upload_run_active:
                return self._project_store.load_upload_records(project_id)
            active_records = self._load_records(project_id, records)
            self._active_project = project
            self._cached_records = active_records
            quota_state = self._load_quota_state()
            current_time = now_utc or datetime.now(UTC)
            if current_time < quota_state.reset_timestamp_utc:
                self._persist_state(project_id, active_records, quota_state)
                return active_records

            quota_state = quota_state.reset()
            self._release_queued_records_after_reset(active_records)
            self._persist_state(project_id, active_records, quota_state)
            return self.start_upload(project, active_records)
        finally:
            self._run_lock.release()

    def resume_queued_on_startup(self, project: ConcertProject) -> list[UploadRecord]:
        """Next-launch recovery: load queued uploads and auto-resume when quota allows."""
        project_id = self._project_id(project)
        if not self._run_lock.acquire(blocking=False):
            return self._project_store.load_upload_records(project_id)
        try:
            if self.__class__._is_upload_run_active:
                return self._project_store.load_upload_records(project_id)
            records = self._project_store.load_upload_records(project_id)
            self._active_project = project
            self._recover_orphaned_uploads(project, records)
            if not any(record.upload_status == UploadStatus.QUEUED for record in records):
                self._cached_records = records
                self._persist_state(project_id, records, self._load_quota_state())
                return records
            return self.run_quota_reset_scheduler(project, records)
        finally:
            self._run_lock.release()

    def _process_one_record(
        self,
        *,
        project: ConcertProject,
        record: UploadRecord,
        segments: dict[str, PerformanceSegment],
        mappings: dict[str, VideoMetadataMapping],
        quota_state: QuotaState,
        all_records: list[UploadRecord],
    ) -> QuotaState:
        """Upload a single record with retry, resume, and restart-from-zero handling."""
        segment = segments.get(record.segment_id)
        file_path = segment.exported_file_path if segment is not None else None
        if file_path is None or not Path(file_path).exists():
            record.transition_to(UploadStatus.UPLOADING)
            self._mark_failed(
                record,
                failure_kind="UNKNOWN",
                error_message="Exported segment file not found.",
                restart_from_zero=False,
                session_invalidated_at_utc=None,
            )
            self._write_upload_checkpoint(project, record)
            return quota_state

        record.transition_to(UploadStatus.UPLOADING)
        metadata = self._build_upload_metadata(record, mappings.get(record.mapping_id), file_path)

        retry_count = 0
        session_invalidated_retry_used = False
        while True:
            result = self._upload_service.upload(
                file_path=file_path,
                metadata=metadata,
                progress_callback=lambda uploaded, total: self._on_progress(
                    project=project,
                    record=record,
                    uploaded=uploaded,
                    total=total,
                    all_records=all_records,
                ),
                resumable_uri=record.resumable_upload_uri,
                bytes_uploaded=record.bytes_uploaded,
                session_callback=lambda uri: self._on_session_uri(
                    project=project,
                    record=record,
                    resumable_uri=uri,
                    all_records=all_records,
                ),
            )

            record.resumable_upload_uri = result.resumable_uri
            record.bytes_uploaded = max(record.bytes_uploaded, result.bytes_uploaded)
            if result.error_message:
                record.error_detail = result.error_message
            if result.failure_kind:
                record.failure_kind = result.failure_kind

            if result.success and result.video_id is not None:
                existing_error = record.error_detail
                record.youtube_video_id = result.video_id
                record.youtube_url = f"https://www.youtube.com/watch?v={result.video_id}"
                playlist_error: str | None = None
                if record.playlist_id is not None:
                    try:
                        self._upload_service.add_to_playlist(record.playlist_id, result.video_id)
                    except Exception as exc:
                        playlist_error = f"playlist_assignment_failed:{exc}"
                if playlist_error is not None:
                    record.error_detail = playlist_error
                elif (
                    isinstance(existing_error, str)
                    and existing_error.startswith("playlist_creation_failed:")
                ):
                    record.error_detail = existing_error
                else:
                    record.error_detail = None
                record.failure_kind = None
                record.restart_from_zero = False
                record.session_invalidated_at_utc = None
                record.transition_to(UploadStatus.COMPLETED)
                self._write_upload_checkpoint(project, record)
                return quota_state.record_upload(record.quota_cost)

            if result.failure_kind == "QUOTA_EXHAUSTED":
                self._queue_record(record, result.error_message or "Daily quota exhausted; queued until reset.")
                self._write_upload_checkpoint(project, record)
                return self._mark_quota_exhausted(quota_state)

            should_restart = (
                result.failure_kind == "SESSION_INVALIDATED" and not session_invalidated_retry_used
            )
            should_retry = result.resume_allowed and retry_count < self._max_retries
            if should_restart:
                retry_count += 1
                record.retry_count = retry_count
                record.restart_from_zero = True
                record.session_invalidated_at_utc = result.session_invalidated_at_utc or datetime.now(UTC)
                record.resumable_upload_uri = None
                record.bytes_uploaded = 0
                session_invalidated_retry_used = True
                self._write_upload_checkpoint(project, record)
                continue

            if should_retry:
                retry_count += 1
                record.retry_count = retry_count
                self._write_upload_checkpoint(project, record)
                continue

            self._mark_failed(
                record,
                failure_kind=result.failure_kind or "UNKNOWN",
                error_message=result.error_message or "Upload failed.",
                restart_from_zero=result.restart_from_zero,
                session_invalidated_at_utc=result.session_invalidated_at_utc,
            )
            self._write_upload_checkpoint(project, record)
            return quota_state

    def _build_upload_metadata(
        self,
        record: UploadRecord,
        mapping: VideoMetadataMapping | None,
        file_path: Path,
    ) -> UploadMetadata:
        """Compose UploadMetadata while preserving FR-050 required fields."""
        title = mapping.final_title.strip() if mapping and mapping.final_title.strip() else file_path.stem
        description = mapping.final_description if mapping is not None else ""
        tags = list(mapping.final_tags) if mapping is not None else []
        privacy = mapping.final_privacy if mapping is not None else record.privacy_setting
        category_id = mapping.final_category_id if mapping and mapping.final_category_id else "10"
        record.privacy_setting = privacy
        return UploadMetadata(
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy,
            category_id=category_id,
            playlist_id=record.playlist_id,
        )

    def _assign_playlist_if_needed(self, project: ConcertProject, records: list[UploadRecord]) -> None:
        """Assign deterministic playlist ID to uploads lacking explicit playlist assignment."""
        missing_playlist = [record for record in records if record.playlist_id is None]
        if not missing_playlist:
            return

        existing_ids = [record.playlist_id for record in records if record.playlist_id]
        if existing_ids:
            playlist_id = existing_ids[0]
        else:
            try:
                playlist_id = self._upload_service.create_playlist(
                    title=project.name,
                    description=f"{project.name} upload set",
                    privacy=PrivacySetting.PUBLIC,
                )
            except Exception as exc:
                for record in missing_playlist:
                    record.error_detail = f"playlist_creation_failed:{exc}"
                return
        for record in sorted(missing_playlist, key=lambda item: item.id):
            record.playlist_id = playlist_id

    def _mark_failed(
        self,
        record: UploadRecord,
        *,
        failure_kind: str,
        error_message: str,
        restart_from_zero: bool,
        session_invalidated_at_utc: datetime | None,
    ) -> None:
        """Apply failed-state diagnostics while honoring UploadRecord invariants."""
        if failure_kind == "SESSION_INVALIDATED":
            record.session_invalidated_at_utc = session_invalidated_at_utc or datetime.now(UTC)
            record.restart_from_zero = True
            record.bytes_uploaded = 0
            record.resumable_upload_uri = None
        else:
            record.restart_from_zero = restart_from_zero and failure_kind == "SESSION_INVALIDATED"
            record.session_invalidated_at_utc = session_invalidated_at_utc
            if restart_from_zero:
                record.bytes_uploaded = 0
                record.resumable_upload_uri = None
        record.failure_kind = failure_kind
        record.error_detail = error_message
        record.transition_to(UploadStatus.FAILED)

    def _queue_record(self, record: UploadRecord, message: str) -> None:
        """Move record to queue state for quota reset auto-resume."""
        if (
            record.upload_status != UploadStatus.QUEUED
            and record.upload_status in {UploadStatus.PENDING, UploadStatus.UPLOADING}
        ):
            record.transition_to(UploadStatus.QUEUED)
        if record.restart_from_zero:
            record.resumable_upload_uri = None
            record.bytes_uploaded = 0
        record.restart_from_zero = False
        record.session_invalidated_at_utc = None
        record.failure_kind = "QUOTA_EXHAUSTED"
        record.error_detail = message

    def _on_progress(
        self,
        *,
        project: ConcertProject,
        record: UploadRecord,
        uploaded: int,
        total: int,
        all_records: list[UploadRecord],
    ) -> None:
        """Persist acknowledged upload progress for resumable continuation."""
        del total
        record.bytes_uploaded = max(record.bytes_uploaded, uploaded)
        self._write_upload_checkpoint(project, record)
        self._project_store.save_upload_records(self._project_id(project), all_records)

    def _on_session_uri(
        self,
        *,
        project: ConcertProject,
        record: UploadRecord,
        resumable_uri: str,
        all_records: list[UploadRecord],
    ) -> None:
        """Persist resumable upload URI as soon as provider returns/refreshes it."""
        record.resumable_upload_uri = resumable_uri
        self._write_upload_checkpoint(project, record)
        self._project_store.save_upload_records(self._project_id(project), all_records)

    def _queue_pending_for_auth_retry(
        self,
        records: list[UploadRecord],
        project: ConcertProject,
        quota_state: QuotaState,
    ) -> None:
        """Queue pending uploads when authentication is temporarily unavailable."""
        for record in records:
            if record.upload_status != UploadStatus.PENDING:
                continue
            record.transition_to(UploadStatus.QUEUED)
            record.failure_kind = "AUTH_FAILURE"
            record.error_detail = "Authentication failed; queued for retry."
            self._write_upload_checkpoint(project, record)
        self._persist_state(self._project_id(project), records, quota_state)

    def _load_records(
        self,
        project_id: str,
        records: list[UploadRecord] | None,
    ) -> list[UploadRecord]:
        """Resolve upload records from explicit input or project persistence."""
        if records is not None:
            return records
        return self._project_store.load_upload_records(project_id)

    def _load_quota_state(self) -> QuotaState:
        """Load quota state or initialize a default snapshot."""
        state = self._quota_state_store.load()
        if state is not None:
            self._quota_state_cache = state
            return state
        now = datetime.now(UTC)
        state = QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=pt_midnight_utc(),
            last_updated=now,
        )
        self._quota_state_cache = state
        return state

    def _reset_quota_if_due(self, quota_state: QuotaState) -> tuple[QuotaState, bool]:
        """Reset quota when reset timestamp has passed."""
        current_time = datetime.now(UTC)
        reset_state = quota_state
        reset_applied = False
        while current_time >= reset_state.reset_timestamp_utc:
            reset_state = reset_state.reset()
            reset_applied = True
        if not reset_applied:
            return quota_state, False
        self._quota_state_cache = reset_state
        return reset_state, True

    @staticmethod
    def _release_queued_records_after_reset(records: list[UploadRecord]) -> None:
        """Apply queued→pending transitions while preserving resumable state rules."""
        for record in records:
            if record.upload_status != UploadStatus.QUEUED:
                continue
            record.transition_to(UploadStatus.PENDING)
            if record.failure_kind == "SESSION_INVALIDATED":
                record.resumable_upload_uri = None
                record.bytes_uploaded = 0
                record.restart_from_zero = False
                record.session_invalidated_at_utc = None
            record.error_detail = None
            record.failure_kind = None

    @staticmethod
    def _release_auth_queued_records(records: list[UploadRecord]) -> None:
        """Release records queued only because authentication was temporarily unavailable."""
        for record in records:
            if record.upload_status != UploadStatus.QUEUED:
                continue
            if record.failure_kind != "AUTH_FAILURE":
                continue
            record.transition_to(UploadStatus.PENDING)
            record.failure_kind = None
            record.error_detail = None

    def _recover_orphaned_uploads(
        self,
        project: ConcertProject,
        records: list[UploadRecord],
    ) -> None:
        """Recover records left in UPLOADING by interrupted prior sessions."""
        for record in records:
            if record.upload_status != UploadStatus.UPLOADING:
                continue
            self._mark_failed(
                record,
                failure_kind="UNKNOWN",
                error_message="Upload interrupted by previous session.",
                restart_from_zero=False,
                session_invalidated_at_utc=None,
            )
            self._write_upload_checkpoint(project, record)

    @staticmethod
    def _sorted_records(
        records: list[UploadRecord],
        segments: dict[str, PerformanceSegment],
    ) -> list[UploadRecord]:
        """Sort records deterministically by segment index then record ID."""
        return sorted(
            records,
            key=lambda record: (
                segments[record.segment_id].segment_index if record.segment_id in segments else 10_000,
                record.id,
            ),
        )

    def _segments_by_id(self, project_id: str) -> dict[str, PerformanceSegment]:
        """Load project segments keyed by segment UUID text."""
        return {str(segment.id): segment for segment in self._project_store.load_segments(project_id)}

    def _mappings_by_id(self, project_id: str) -> dict[str, VideoMetadataMapping]:
        """Load project mappings keyed by mapping UUID text."""
        return {str(mapping.id): mapping for mapping in self._project_store.load_mappings(project_id)}

    def _write_upload_checkpoint(self, project: ConcertProject, record: UploadRecord) -> None:
        """Persist per-upload checkpoint snapshots (FR-040)."""
        checkpoint = Checkpoint(
            id=uuid4(),
            project_id=self._project_id(project),
            stage=PipelineStage.UPLOAD,
            status=CheckpointStatus.VALID,
            created_at=datetime.now(UTC),
            input_hashes={
                "record_id": record.id,
                "bytes_uploaded": str(record.bytes_uploaded),
            },
            config_snapshot=asdict(project.config_snapshot),
            model_versions={"upload_service": self._upload_service.__class__.__name__},
            output_references=[
                f"status:{record.upload_status.value}",
                f"video_id:{record.youtube_video_id}" if record.youtube_video_id else "video_id:none",
                f"resumable_uri:{record.resumable_upload_uri}" if record.resumable_upload_uri else "resumable_uri:none",
            ],
            segment_index=self._segment_index(record.segment_id, self._segments_by_id(self._project_id(project))),
            error_detail=record.error_detail,
        )
        self._checkpoint_manager.save_checkpoint(checkpoint)

    @staticmethod
    def _segment_index(
        segment_id: str,
        segments: dict[str, PerformanceSegment],
    ) -> int | None:
        """Resolve segment index for checkpoint addressing."""
        segment = segments.get(segment_id)
        if segment is None:
            return None
        return segment.segment_index

    def _persist_state(
        self,
        project_id: str,
        records: list[UploadRecord],
        quota_state: QuotaState,
    ) -> None:
        """Persist queue and quota state snapshots."""
        self._project_store.save_upload_records(project_id, records)
        self._quota_state_store.save(quota_state)
        self._quota_state_cache = quota_state
        self._cached_records = records

    @staticmethod
    def _mark_quota_exhausted(quota_state: QuotaState) -> QuotaState:
        """Set local quota snapshot to exhausted after provider quota rejection."""
        return replace(
            quota_state,
            daily_used=quota_state.daily_limit,
            last_updated=datetime.now(UTC),
        )

    @staticmethod
    def _project_id(project: ConcertProject) -> str:
        """Normalize project UUID for persistence boundaries."""
        return str(project.id)
