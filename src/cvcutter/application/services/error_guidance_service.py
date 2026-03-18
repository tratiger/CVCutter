from __future__ import annotations


def map_error_to_guidance(recoverable: bool, *, error_code: str = "unknown") -> dict[str, str]:
    if recoverable:
        return {
            "label": "recoverable",
            "next_action": "retry",
            "reason": error_code,
            "message": "Temporary issue detected. Retry is recommended.",
        }
    return {
        "label": "blocking",
        "next_action": "check_settings",
        "reason": error_code,
        "message": "Blocking issue detected. Update configuration before retry.",
    }
