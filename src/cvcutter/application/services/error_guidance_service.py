from __future__ import annotations


def map_error_to_guidance(recoverable: bool) -> dict[str, str]:
    if recoverable:
        return {"label": "recoverable", "next_action": "retry"}
    return {"label": "blocking", "next_action": "check_settings"}
