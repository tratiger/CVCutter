from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _pacific_tz() -> ZoneInfo | timezone:
    """Return Pacific timezone info, with a fixed-offset fallback if tzdata is unavailable."""
    try:
        return ZoneInfo("America/Los_Angeles")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-8))


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS when needed, otherwise MM:SS."""
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_timestamp(dt: datetime) -> str:
    """Format a datetime value as an ISO 8601 string."""
    return dt.isoformat()


def parse_timestamp(s: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a datetime."""
    return datetime.fromisoformat(s)


def seconds_to_timecode(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm timecode."""
    total_milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def pt_midnight_utc() -> datetime:
    """Return the next Pacific Time midnight converted to UTC."""
    now_pt = datetime.now(_pacific_tz())
    next_midnight_pt = (now_pt + timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return next_midnight_pt.astimezone(UTC)
