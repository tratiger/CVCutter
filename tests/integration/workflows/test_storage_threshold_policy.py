from cvcutter.application.services.storage_safety_service import evaluate_storage_policy


def test_storage_thresholds() -> None:
    assert evaluate_storage_policy(19) == "warning"
    assert evaluate_storage_policy(9) == "start_blocked"
    assert evaluate_storage_policy(4) == "safe_pause"


def test_storage_recovery_requires_explicit_operator_confirmation() -> None:
    assert (
        evaluate_storage_policy(15, recovered_from_block=True, operator_confirmed=False)
        == "confirmation_required"
    )
    assert evaluate_storage_policy(15, recovered_from_block=True, operator_confirmed=True) == "warning"
    assert (
        evaluate_storage_policy(25, recovered_from_block=True, operator_confirmed=False)
        == "confirmation_required"
    )
    assert evaluate_storage_policy(25, recovered_from_block=True, operator_confirmed=True) == "ok"
