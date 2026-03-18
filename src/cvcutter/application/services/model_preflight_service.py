from __future__ import annotations


def evaluate_model_availability(model_available: bool, *, viable_modalities: int = 1) -> str:
    if model_available:
        return "full_confidence"
    if viable_modalities <= 0:
        return "blocked_no_viable_modality"
    return "reduced_confidence"
