from cvcutter.application.services.model_preflight_service import evaluate_model_availability


def test_model_availability_fallback() -> None:
    assert evaluate_model_availability(False) == "reduced_confidence"


def test_model_availability_blocks_when_no_viable_modality() -> None:
    assert evaluate_model_availability(False, viable_modalities=0) == "blocked_no_viable_modality"
