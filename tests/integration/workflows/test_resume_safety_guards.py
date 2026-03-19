from cvcutter.application.services.config_change_guard_service import ConfigChangeGuardService
from cvcutter.application.services.startup_recovery_service import (
    StartupRecoveryService,
    can_start_new_job,
    detect_stale_state,
    recover_startup_state,
)


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


def test_stale_running_state_recovers_via_paused_then_resumable() -> None:
    result = recover_startup_state(
        current_state="running",
        last_heartbeat_seconds=600,
        worker_alive=False,
    )
    assert result["state"] == "resumable"
    assert result["transitions"] == ["paused", "resumable"]


def test_stale_running_state_does_not_force_resume_when_worker_is_alive() -> None:
    result = recover_startup_state(
        current_state="running",
        last_heartbeat_seconds=600,
        worker_alive=True,
    )
    assert result["state"] == "running"
    assert result["transitions"] == []


def test_startup_recovery_service_updates_persisted_job_state(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111161"
    sqlite_repo.insert_job(job_id, "running", "operator")
    service = StartupRecoveryService(sqlite_repo)

    result = service.recover_job_state(
        job_id=job_id,
        last_heartbeat_seconds=600,
        worker_alive=False,
    )

    assert result["state"] == "resumable"
    assert sqlite_repo.get_job_state(job_id) == "resumable"
