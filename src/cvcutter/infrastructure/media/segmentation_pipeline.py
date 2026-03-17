from __future__ import annotations


def detect_acceleration(capabilities: set[str]) -> bool:
    return "gpu" in capabilities


def segment_stream(frames: list[int], acceleration: bool) -> list[tuple[int, int]]:
    _ = acceleration
    if not frames:
        return []
    return [(0, len(frames) - 1)]
