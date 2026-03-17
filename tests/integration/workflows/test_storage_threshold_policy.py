from cvcutter.application.services.storage_safety_service import evaluate_storage_policy


def test_storage_thresholds() -> None:
    assert evaluate_storage_policy(19) == "warning"
    assert evaluate_storage_policy(9) == "start_blocked"
    assert evaluate_storage_policy(4) == "safe_pause"
