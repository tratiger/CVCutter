"""Upload-related entities for segment upload lifecycle and quota tracking."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from cvcutter.shared.types import PrivacySetting, UploadStatus

_UPLOAD_STATE_TRANSITIONS: dict[UploadStatus, set[UploadStatus]] = {
    UploadStatus.PENDING: {UploadStatus.UPLOADING, UploadStatus.QUEUED},
    UploadStatus.UPLOADING: {
        UploadStatus.UPLOADING,
        UploadStatus.COMPLETED,
        UploadStatus.FAILED,
        UploadStatus.QUEUED,
    },
    UploadStatus.QUEUED: {UploadStatus.PENDING},
    UploadStatus.FAILED: {UploadStatus.PENDING},
    UploadStatus.COMPLETED: set(),
}


def _validate_uuid_text(value: str, field_name: str) -> None:
    """Validate a UUID string field."""
    try:
        UUID(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid UUID string.") from exc


@dataclass
class UploadRecord:
    """Upload lifecycle record for one exported performance segment."""

    id: str
    segment_id: str
    mapping_id: str
    youtube_video_id: str | None = None
    upload_status: UploadStatus = UploadStatus.PENDING
    privacy_setting: PrivacySetting = PrivacySetting.PUBLIC
    playlist_id: str | None = None
    quota_cost: int = 1600
    retry_count: int = 0
    error_detail: str | None = None
    resumable_upload_uri: str | None = None
    bytes_uploaded: int = 0
    failure_kind: str | None = None
    session_invalidated_at_utc: datetime | None = None
    restart_from_zero: bool = False
    youtube_url: str | None = None
    uploaded_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate upload-record invariants."""
        _validate_uuid_text(self.id, "id")
        _validate_uuid_text(self.segment_id, "segment_id")
        _validate_uuid_text(self.mapping_id, "mapping_id")

        if self.quota_cost <= 0:
            raise ValueError("quota_cost must be positive.")
        if self.retry_count < 0:
            raise ValueError("retry_count must be >= 0.")
        if self.bytes_uploaded < 0:
            raise ValueError("bytes_uploaded must be >= 0.")
        if self.upload_status == UploadStatus.FAILED and not self.error_detail:
            raise ValueError("error_detail is required when upload_status is FAILED.")
        if self.failure_kind == "SESSION_INVALIDATED" and self.session_invalidated_at_utc is None:
            raise ValueError(
                "session_invalidated_at_utc is required when failure_kind is SESSION_INVALIDATED.",
            )
        if self.restart_from_zero and self.failure_kind != "SESSION_INVALIDATED":
            raise ValueError("restart_from_zero requires failure_kind to be SESSION_INVALIDATED.")
        if self.restart_from_zero and not self.error_detail:
            raise ValueError("error_detail is required when restart_from_zero is True.")

    def transition_to(self, new_status: UploadStatus) -> None:
        """Transition upload status while enforcing state-machine rules."""
        if new_status == self.upload_status:
            return

        allowed_statuses = _UPLOAD_STATE_TRANSITIONS[self.upload_status]
        if new_status not in allowed_statuses:
            raise ValueError(f"Invalid upload transition: {self.upload_status.value} -> {new_status.value}")

        if new_status == UploadStatus.PENDING and self.upload_status in {
            UploadStatus.FAILED,
            UploadStatus.QUEUED,
        }:
            self.retry_count = 0

        if new_status == UploadStatus.COMPLETED:
            self.uploaded_at = datetime.now(UTC)
            if self.youtube_video_id and not self.youtube_url:
                self.youtube_url = f"https://www.youtube.com/watch?v={self.youtube_video_id}"

        self.upload_status = new_status


@dataclass(frozen=True)
class QuotaState:
    """Immutable snapshot of YouTube API daily quota usage."""

    daily_limit: int = 10_000
    daily_used: int = 0
    reset_timestamp_utc: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate quota-state invariants."""
        if self.daily_limit <= 0:
            raise ValueError("daily_limit must be positive.")
        if self.daily_used < 0:
            raise ValueError("daily_used must be >= 0.")
        if self.daily_used > self.daily_limit:
            raise ValueError("daily_used must not exceed daily_limit.")

    def can_upload(self, cost: int = 1600) -> bool:
        """Return True when enough quota remains for a new upload."""
        if cost <= 0:
            raise ValueError("cost must be positive.")
        return (self.daily_used + cost) <= self.daily_limit

    def record_upload(self, cost: int) -> QuotaState:
        """Return a new QuotaState after consuming quota for one upload."""
        if not self.can_upload(cost):
            raise ValueError("Insufficient quota for requested upload cost.")
        return replace(
            self,
            daily_used=self.daily_used + cost,
            last_updated=datetime.now(UTC),
        )

    def reset(self) -> QuotaState:
        """Return a new QuotaState reset for the next quota period."""
        now = datetime.now(UTC)
        return replace(
            self,
            daily_used=0,
            reset_timestamp_utc=self.reset_timestamp_utc + timedelta(days=1),
            last_updated=now,
        )

    def uploads_remaining(self, cost: int = 1600) -> int:
        """Return how many uploads remain for a given per-upload cost."""
        if cost <= 0:
            raise ValueError("cost must be positive.")
        remaining_units = max(0, self.daily_limit - self.daily_used)
        return remaining_units // cost
