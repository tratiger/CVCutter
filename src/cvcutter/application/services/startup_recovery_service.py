from __future__ import annotations


def detect_stale_state(last_heartbeat_seconds: int, threshold_seconds: int = 300) -> bool:
    return last_heartbeat_seconds > threshold_seconds


def can_start_new_job(has_stale_lock: bool) -> bool:
    return not has_stale_lock
