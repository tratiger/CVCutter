from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProcessingEvent:
    event_type: str
    job_id: str | None
    payload: dict[str, object]
