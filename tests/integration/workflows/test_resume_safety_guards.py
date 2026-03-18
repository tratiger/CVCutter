from cvcutter.application.services.config_change_guard_service import ConfigChangeGuardService
from cvcutter.application.services.startup_recovery_service import can_start_new_job, detect_stale_state


def test_startup_stale_state_detection() -> None:
    assert detect_stale_state(301)
    assert not can_start_new_job(True)


def test_resume_gate_after_config_change() -> None:
    guard = ConfigChangeGuardService()
    assert guard.assess({"classification_strategy"}, "map_metadata") == "decision_required"
    assert guard.assess({"metadata_source_refs.event_schedule"}, "publish") == "decision_required"
    assert guard.assess({"low_confidence_threshold"}, "publish") == "decision_required"
    assert guard.assess({"output_prefs.title_overlay"}, "sync") == "continue"
    assert guard.assess({"output_prefs.title_overlay"}, "map") == "continue"
    assert guard.assess({"unknown.runtime.flag"}, "publish") == "continue"
