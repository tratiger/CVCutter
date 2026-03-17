from __future__ import annotations


def evaluate_model_availability(model_available: bool) -> str:
    return "full_confidence" if model_available else "reduced_confidence"
