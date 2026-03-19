from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MediaSegmentCandidate:
    segment_id: str
    job_id: str
    start_ms: int
    end_ms: int
    confidence_score: int
    requires_review: bool
    review_status: str = "pending"
    modality_scores: dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.start_ms >= self.end_ms:
            raise ValueError("start_ms must be less than end_ms")
        if self.confidence_score < 0 or self.confidence_score > 100:
            raise ValueError("confidence_score must be between 0 and 100")
        if self.review_status not in {"pending", "accepted", "adjusted", "rejected"}:
            raise ValueError("invalid_review_status")


@dataclass(slots=True)
class AudioSourceProfile:
    audio_profile_id: str
    job_id: str
    source_name: str
    source_kind: str
    offset_ms: int
    gain_db: float = 0.0
    noise_reduction_level: float = 0.0
    tuning_mode: str = "simple"
    quality_status: str = "ok"
    correction_resolution_status: str = "not_required"

    def __post_init__(self) -> None:
        if self.source_kind not in {"embedded_video", "external"}:
            raise ValueError("invalid_source_kind")
        if self.noise_reduction_level < 0.0 or self.noise_reduction_level > 1.0:
            raise ValueError("noise_reduction_level must be between 0.0 and 1.0")
        if self.tuning_mode not in {"simple", "waveform"}:
            raise ValueError("invalid_tuning_mode")
        if self.quality_status not in {"ok", "flagged_manual_correction"}:
            raise ValueError("invalid_quality_status")
        if self.correction_resolution_status not in {
            "not_required",
            "pending_correction",
            "corrected",
        }:
            raise ValueError("invalid_correction_resolution_status")


@dataclass(slots=True)
class MetadataMappingRecord:
    mapping_id: str
    job_id: str
    segment_id: str
    schema_version: str
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    publish_visibility: str = "private"
    source_trace: dict[str, object] = field(default_factory=dict)
    validation_status: str = "valid"

    def __post_init__(self) -> None:
        if self.publish_visibility not in {"public", "unlisted", "private"}:
            raise ValueError("invalid_publish_visibility")
        if self.validation_status not in {"valid", "invalid"}:
            raise ValueError("invalid_validation_status")


@dataclass(slots=True)
class PublishingTask:
    publish_task_id: str
    job_id: str
    segment_id: str
    destination: str
    status: str = "pending"
    attempt_count: int = 0
    first_transient_failure_at: datetime | None = None
    next_retry_at: datetime | None = None
    external_object_id: str | None = None
    last_error_code: str | None = None

    def __post_init__(self) -> None:
        if self.destination != "youtube":
            raise ValueError("invalid_destination")
        if self.status not in {
            "pending",
            "uploading",
            "retry_waiting",
            "completed",
            "failed_manual_intervention",
        }:
            raise ValueError("invalid_publish_status")
        if self.attempt_count < 0:
            raise ValueError("attempt_count must be >= 0")


@dataclass(slots=True)
class JobDraftLock:
    lock_id: str
    job_id: str
    owner_instance_id: str
    owner_display_name: str
    locked_at: datetime = field(default_factory=_utc_now)
    heartbeat_at: datetime = field(default_factory=_utc_now)
    status: str = "active"

    def __post_init__(self) -> None:
        if self.status not in {"active", "stale", "released"}:
            raise ValueError("invalid_lock_status")


@dataclass(slots=True)
class ConfigurationChangeRecord:
    change_id: str
    job_id: str
    changed_fields: list[str]
    dependency_impact: list[str]
    decision: str
    confirmed_by_operator: bool = False
    confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.decision not in {"invalidate_and_continue", "cancel_resume"}:
            raise ValueError("invalid_config_change_decision")


@dataclass(slots=True)
class OperatorRolePolicy:
    policy_id: str
    job_id: str
    executable_role: str = "operator"
    context_labels: list[str] = field(default_factory=list)
    recorded_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if self.executable_role != "operator":
            raise ValueError("executable_role must be operator")
        invalid_labels = set(self.context_labels) - {"editor", "publisher"}
        if invalid_labels:
            raise ValueError("invalid_context_label")
