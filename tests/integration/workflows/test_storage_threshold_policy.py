from pathlib import Path

from cvcutter.application.services.storage_safety_service import (
    evaluate_storage_policy,
    evaluate_storage_policy_for_path,
)


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


def test_storage_hard_thresholds_override_confirmation_state() -> None:
    assert evaluate_storage_policy(9, recovered_from_block=True, operator_confirmed=False) == "start_blocked"
    assert evaluate_storage_policy(9, recovered_from_block=True, operator_confirmed=True) == "start_blocked"
    assert evaluate_storage_policy(4, recovered_from_block=True, operator_confirmed=False) == "safe_pause"
    assert evaluate_storage_policy(4, recovered_from_block=True, operator_confirmed=True) == "safe_pause"


def test_storage_policy_reads_disk_usage_from_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "cvcutter.application.services.storage_safety_service.read_free_gb",
        lambda _path: 18,
    )
    free_gb, policy = evaluate_storage_policy_for_path(tmp_path)
    assert free_gb == 18
    assert policy == "warning"
