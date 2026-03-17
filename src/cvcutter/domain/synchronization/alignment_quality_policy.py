from __future__ import annotations


def is_alignment_within_tolerance(offset_ms: int, tolerance_ms: int = 80) -> bool:
    return abs(offset_ms) <= tolerance_ms
