from __future__ import annotations


def evaluate_storage_policy(free_gb: int) -> str:
    if free_gb < 5:
        return "safe_pause"
    if free_gb < 10:
        return "start_blocked"
    if free_gb < 20:
        return "warning"
    return "ok"
