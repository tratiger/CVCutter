from __future__ import annotations

from cvcutter.domain.classification.timestamp_validator import validate_timestamp_strategy


def test_timestamp_strategy_accepts_recording_time_inside_event_window() -> None:
    result = validate_timestamp_strategy(
        strategy="timestamp_based",
        recording_time_iso="2026-03-14T18:05:00+09:00",
        event_window_start_iso="2026-03-14T18:00:00+09:00",
        event_window_end_iso="2026-03-14T21:00:00+09:00",
    )
    assert result.ok
    assert result.confidence_state == "confident"
    assert result.reason_codes == []


def test_timestamp_strategy_blocks_when_recording_time_is_missing() -> None:
    result = validate_timestamp_strategy(
        strategy="timestamp_based",
        recording_time_iso=None,
        event_window_start_iso="2026-03-14T18:00:00+09:00",
        event_window_end_iso="2026-03-14T21:00:00+09:00",
    )
    assert not result.ok
    assert result.confidence_state == "blocked_invalid_metadata"
    assert "missing_recording_time" in result.reason_codes


def test_timestamp_strategy_blocks_when_recording_time_is_invalid_iso8601() -> None:
    result = validate_timestamp_strategy(
        strategy="timestamp_based",
        recording_time_iso="2026/03/14 18:05:00",
        event_window_start_iso="2026-03-14T18:00:00+09:00",
        event_window_end_iso="2026-03-14T21:00:00+09:00",
    )
    assert not result.ok
    assert "invalid_recording_time_format" in result.reason_codes


def test_timestamp_strategy_blocks_when_event_window_is_not_derivable() -> None:
    result = validate_timestamp_strategy(
        strategy="timestamp_based",
        recording_time_iso="2026-03-14T18:05:00+09:00",
        event_window_start_iso=None,
        event_window_end_iso="2026-03-14T21:00:00+09:00",
    )
    assert not result.ok
    assert "missing_event_window_bounds" in result.reason_codes


def test_timestamp_strategy_blocks_when_recording_time_is_outside_tolerance() -> None:
    result = validate_timestamp_strategy(
        strategy="timestamp_based",
        recording_time_iso="2026-03-14T17:40:00+09:00",
        event_window_start_iso="2026-03-14T18:00:00+09:00",
        event_window_end_iso="2026-03-14T21:00:00+09:00",
    )
    assert not result.ok
    assert "recording_time_out_of_event_window" in result.reason_codes
