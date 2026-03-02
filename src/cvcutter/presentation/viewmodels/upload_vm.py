"""Upload screen view-model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from cvcutter.domain.models.upload import QuotaState, UploadRecord
from cvcutter.shared.types import UploadStatus


class UploadWorkflow(Protocol):
    """Application service contract for upload workflow actions."""

    # TODO(T078): Wire application.upload_workflow.UploadWorkflow adapter including
    # quota-reset auto-resume and per-record failure diagnostics to this protocol.
    def start_upload(self, project_id: str) -> list[UploadRecord]:
        """Start upload batch for a project."""
        ...

    def pause_upload(self) -> None:
        """Pause active upload batch."""
        ...

    def retry_failed(self, upload_record_id: str) -> UploadRecord:
        """Retry one failed upload record."""
        ...

    def quota_state(self) -> QuotaState:
        """Return latest quota state snapshot."""
        ...


@dataclass
class UploadViewModel:
    """State and commands for upload workflow interactions."""

    workflow: UploadWorkflow
    project_id: str
    upload_records: list[UploadRecord] = field(default_factory=list)
    quota_state_snapshot: QuotaState = field(
        default_factory=lambda: QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC),
        ),
    )
    is_uploading: bool = False
    current_operation: str = "アップロード待機中"
    errors: list[str] = field(default_factory=list)
    _upload_lock: Lock = field(default_factory=Lock, repr=False)

    @property
    def queued_count(self) -> int:
        """Return number of queued uploads."""
        return sum(record.upload_status == UploadStatus.QUEUED for record in self.upload_records)

    @property
    def quota_display(self) -> str:
        """Human-readable quota usage display for UI."""
        state = self.quota_state_snapshot
        return f"使用量 {state.daily_used}/{state.daily_limit} (残り {state.uploads_remaining()} 回)"

    @property
    def per_video_urls(self) -> dict[str, str]:
        """Map upload record IDs to available YouTube URLs."""
        return {
            record.id: record.youtube_url
            for record in self.upload_records
            if isinstance(record.youtube_url, str) and record.youtube_url
        }

    def start_upload(self) -> None:
        """Begin batch upload and refresh records/quota state."""
        if not self._upload_lock.acquire(blocking=False):
            return
        try:
            self.is_uploading = True
            self.current_operation = "アップロードを開始しています..."
            self.errors.clear()
            try:
                self.upload_records = self.workflow.start_upload(self.project_id)
            except Exception as exc:
                self.errors.append(f"アップロード開始に失敗しました: {exc}")
                self.current_operation = "アップロード開始に失敗しました。"
                return
            try:
                self.refresh_quota()
            except Exception as exc:
                self.errors.append(f"クォータ情報の更新に失敗しました: {exc}")
                self.current_operation = "アップロードは完了しましたがクォータ取得に失敗しました。"
                return
            self.current_operation = "アップロード処理を完了しました。"
        except Exception as exc:
            self.errors.append(f"アップロード処理に失敗しました: {exc}")
            self.current_operation = "アップロード処理に失敗しました。"
        finally:
            self.is_uploading = False
            self._upload_lock.release()

    def pause(self) -> None:
        """Pause current upload operation."""
        try:
            self.workflow.pause_upload()
        except Exception as exc:
            self.errors.append(f"アップロード一時停止に失敗しました: {exc}")
            self.current_operation = "アップロード一時停止に失敗しました。"
            return
        self.is_uploading = False
        self.current_operation = "アップロードを一時停止しました。"

    def pause_upload(self) -> None:
        """Alias command matching upload contract naming."""
        self.pause()

    def retry_failed(self, upload_record_id: str) -> None:
        """Retry one failed upload and update list state."""
        try:
            updated = self.workflow.retry_failed(upload_record_id)
        except Exception as exc:
            self.errors.append(f"再試行に失敗しました: {exc}")
            self.current_operation = "再試行に失敗しました。"
            return
        for index, current in enumerate(self.upload_records):
            if current.id == upload_record_id:
                self.upload_records[index] = updated
                break
        try:
            self.refresh_quota()
        except Exception as exc:
            self.errors.append(f"クォータ情報の更新に失敗しました: {exc}")
            self.current_operation = "再試行は完了しましたがクォータ取得に失敗しました。"

    def refresh_quota(self) -> None:
        """Refresh cached quota state."""
        self.quota_state_snapshot = self.workflow.quota_state()
