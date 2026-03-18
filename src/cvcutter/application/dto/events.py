from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

_SEVERITIES = {"info", "warning", "error"}
_JOB_SCOPED_PREFIXES = ("job.", "stage.", "retry.", "publish.", "cleanup.")


@dataclass(slots=True)
class ProcessingEvent:
    event_type: str
    job_id: str | None
    payload: dict[str, object]
    severity: str = "info"
    stage_name: str | None = None
    attempt: int | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_schema_version: str = "1"
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))

    @classmethod
    def new(
        cls,
        event_type: str,
        job_id: str | None,
        payload: dict[str, object],
        *,
        severity: str = "info",
        stage_name: str | None = None,
        attempt: int | None = None,
    ) -> ProcessingEvent:
        return cls(
            event_type=event_type,
            job_id=job_id,
            payload=payload,
            severity=severity,
            stage_name=stage_name,
            attempt=attempt,
        )

    def __post_init__(self) -> None:
        if self.severity not in _SEVERITIES:
            raise ValueError(f"unsupported_severity:{self.severity}")
        if self.event_type.startswith(_JOB_SCOPED_PREFIXES) and not self.job_id:
            raise ValueError("job_id_required_for_job_scoped_event")
        if self.event_type.startswith("stage.") and not self.stage_name:
            raise ValueError("stage_name_required_for_stage_event")
        if self.event_type.startswith("retry.") and self.attempt is None:
            raise ValueError("attempt_required_for_retry_event")
        if self.attempt is not None and self.attempt < 1:
            raise ValueError("attempt_must_be_positive")
