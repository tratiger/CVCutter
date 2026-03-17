from cvcutter.application.services.model_preflight_service import evaluate_model_availability


def test_model_availability_fallback() -> None:
    assert evaluate_model_availability(False) == "reduced_confidence"
