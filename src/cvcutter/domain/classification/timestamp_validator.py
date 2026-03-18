from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

_TOLERANCE_MINUTES = 10


@dataclass(slots=True)
class TimestampValidationResult:
    ok: bool
    confidence_state: str
    reason_codes: list[str]
    guidance: str


def validate_timestamp_strategy(
    *,
    strategy: str,
    recording_time_iso: str | None,
    event_window_start_iso: str | None,
    event_window_end_iso: str | None,
) -> TimestampValidationResult:
    if strategy != "timestamp_based":
        return TimestampValidationResult(True, "confident", [], "ok")

    if not recording_time_iso:
        return _blocked("missing_recording_time", "provide_recording_time_or_switch_strategy")

    recording_time = _parse_iso8601(recording_time_iso)
    if recording_time is None:
        return _blocked("invalid_recording_time_format", "provide_timezone_aware_iso8601")

    if not event_window_start_iso or not event_window_end_iso:
        return _blocked("missing_event_window_bounds", "provide_event_schedule_metadata")

    event_start = _parse_iso8601(event_window_start_iso)
    event_end = _parse_iso8601(event_window_end_iso)
    if event_start is None or event_end is None:
        return _blocked("invalid_event_window_format", "provide_timezone_aware_iso8601_bounds")
    if event_start > event_end:
        return _blocked("invalid_event_window_order", "correct_event_schedule_metadata")

    lower_bound = event_start - timedelta(minutes=_TOLERANCE_MINUTES)
    upper_bound = event_end + timedelta(minutes=_TOLERANCE_MINUTES)
    if recording_time < lower_bound or recording_time > upper_bound:
        return _blocked("recording_time_out_of_event_window", "adjust_metadata_or_switch_strategy")

    return TimestampValidationResult(True, "confident", [], "ok")


def _parse_iso8601(value: str) -> datetime | None:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _blocked(reason: str, guidance: str) -> TimestampValidationResult:
    return TimestampValidationResult(False, "blocked_invalid_metadata", [reason], guidance)
