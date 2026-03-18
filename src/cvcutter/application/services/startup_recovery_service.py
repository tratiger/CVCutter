from __future__ import annotations


def detect_stale_state(last_heartbeat_seconds: int, threshold_seconds: int = 300) -> bool:
    return last_heartbeat_seconds > threshold_seconds


def can_start_new_job(has_stale_lock: bool) -> bool:
    return not has_stale_lock


def recover_startup_state(
    *,
    current_state: str,
    last_heartbeat_seconds: int,
    worker_alive: bool,
) -> dict[str, object]:
    transitions: list[str] = []
    if current_state == "running" and detect_stale_state(last_heartbeat_seconds) and not worker_alive:
        transitions.append("paused")
        transitions.append("resumable")
        return {"state": "resumable", "transitions": transitions}
    return {"state": current_state, "transitions": transitions}
