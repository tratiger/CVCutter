from cvcutter.application.services.error_guidance_service import map_error_to_guidance


def test_error_recoverability_labels() -> None:
    assert map_error_to_guidance(True)["label"] == "recoverable"
