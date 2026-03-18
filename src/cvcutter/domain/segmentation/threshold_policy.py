from __future__ import annotations


def low_confidence_threshold(configured_threshold: int | None = None) -> int:
    if configured_threshold is None:
        return 70
    if configured_threshold < 0 or configured_threshold > 100:
        raise ValueError("low_confidence_threshold must be between 0 and 100")
    return configured_threshold
