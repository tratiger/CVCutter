from __future__ import annotations


def is_alignment_within_tolerance(offset_ms: int, tolerance_ms: int = 80) -> bool:
    return abs(offset_ms) <= tolerance_ms


def evaluate_alignment_quality(offset_samples_ms: list[int], tolerance_ms: int = 80) -> dict[str, int | str]:
    if not offset_samples_ms:
        return {"median_error_ms": 0, "status": "ok"}
    ordered = sorted(abs(sample) for sample in offset_samples_ms)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 0:
        median = int((ordered[middle - 1] + ordered[middle]) / 2)
    else:
        median = ordered[middle]
    status = "ok" if median <= tolerance_ms else "flagged_manual_correction"
    return {"median_error_ms": median, "status": status}
