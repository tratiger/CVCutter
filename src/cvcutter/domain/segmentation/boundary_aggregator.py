from __future__ import annotations

from statistics import mean


def aggregate_boundaries(candidates: list[tuple[float, float]]) -> float:
    if not candidates:
        return 0.0
    weighted_sum = sum(position * confidence for position, confidence in candidates)
    weight_total = sum(confidence for _, confidence in candidates)
    if weight_total <= 0:
        return mean(position for position, _ in candidates)
    return weighted_sum / weight_total
