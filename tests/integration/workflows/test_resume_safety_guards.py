from cvcutter.application.services.config_change_guard_service import ConfigChangeGuardService
from cvcutter.application.services.startup_recovery_service import can_start_new_job, detect_stale_state


def test_startup_stale_state_detection() -> None:
    assert detect_stale_state(301)
    assert not can_start_new_job(True)


def test_resume_gate_after_config_change() -> None:
    guard = ConfigChangeGuardService()
    assert guard.assess({"sync.reference"}, "sync") == "decision_required"
    assert guard.assess({"segmentation.threshold"}, "sync") == "decision_required"
