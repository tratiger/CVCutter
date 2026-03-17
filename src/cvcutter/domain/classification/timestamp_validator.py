from __future__ import annotations


def validate_timestamp_strategy(has_embedded_timestamp: bool, strategy: str) -> tuple[bool, str]:
    if strategy == "embedded" and not has_embedded_timestamp:
        return False, "embedded timestamp missing"
    return True, "ok"
