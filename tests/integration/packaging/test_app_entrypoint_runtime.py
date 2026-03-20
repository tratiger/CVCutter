from __future__ import annotations

from pathlib import Path

from cvcutter.app import AppBootstrap, run_runtime
from cvcutter.infrastructure.packaging.platform_compatibility import PlatformCompatibilityChecker
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories
from cvcutter.presentation.flet_app.views.onboarding_view import OnboardingView


class _SupportedChecker(PlatformCompatibilityChecker):
    def ensure_supported(self) -> dict[str, str | bool]:
        return {"supported": True, "reason": "ok"}


class _UnsupportedChecker(PlatformCompatibilityChecker):
    def ensure_supported(self) -> dict[str, str | bool]:
        return {"supported": False, "reason": "unsupported_os"}


class _RecoveredChecker(PlatformCompatibilityChecker):
    def ensure_supported(self) -> dict[str, str | bool]:
        return {
            "supported": True,
            "reason": "ok",
            "recovered_from_block": True,
            "operator_confirmed": False,
        }


def test_run_runtime_executes_onboarding(monkeypatch) -> None:
    observed: dict[str, bool] = {"ran": False}

    def _run(self: OnboardingView) -> str:
        observed["ran"] = True
        return "create_first_draft"

    monkeypatch.setattr(OnboardingView, "run", _run)
    exit_code = run_runtime(AppBootstrap(checker=_SupportedChecker()))
    assert exit_code == 0
    assert observed["ran"]


def test_run_runtime_blocks_on_unsupported_platform() -> None:
    exit_code = run_runtime(AppBootstrap(checker=_UnsupportedChecker()))
    assert exit_code == 1


def test_launch_recovers_running_jobs_before_onboarding(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    repo = SqliteRepositories(db_path)
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111171"
    repo.insert_job(job_id, "running", "operator")

    bootstrap = AppBootstrap(
        checker=_SupportedChecker(),
        repositories=repo,
        runtime_path=str(tmp_path),
    )
    launch_result = bootstrap.launch()
    assert launch_result["status"] == "ready"
    assert repo.get_job_state(job_id) == "resumable"


def test_launch_does_not_force_recovery_when_active_job_lock_is_owned(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    repo = SqliteRepositories(db_path)
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111172"
    repo.insert_job(job_id, "running", "operator")
    assert repo.acquire_active_job_lock(job_id)

    bootstrap = AppBootstrap(
        checker=_SupportedChecker(),
        repositories=repo,
        runtime_path=str(tmp_path),
    )
    launch_result = bootstrap.launch()
    assert launch_result["status"] == "ready"
    assert repo.get_job_state(job_id) == "running"


def test_launch_recovers_running_job_when_lock_heartbeat_is_stale(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    repo = SqliteRepositories(db_path)
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111173"
    repo.insert_job(job_id, "running", "operator")
    assert repo.acquire_active_job_lock(job_id)
    conn = repo.connect()
    try:
        conn.execute(
            "UPDATE locks SET heartbeat_at = datetime('now', '-1000 seconds') WHERE lock_name = 'active_job'"
        )
        conn.commit()
    finally:
        conn.close()

    bootstrap = AppBootstrap(
        checker=_SupportedChecker(),
        repositories=repo,
        runtime_path=str(tmp_path),
    )
    launch_result = bootstrap.launch()
    assert launch_result["status"] == "ready"
    assert repo.get_job_state(job_id) == "resumable"


def test_launch_blocks_when_recovery_raises(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "app.db"
    repo = SqliteRepositories(db_path)
    repo.init_schema()
    repo.insert_job("11111111-1111-1111-1111-111111111174", "running", "operator")

    def _raise(*args, **kwargs):
        raise RuntimeError("recovery-failed")

    monkeypatch.setattr(
        "cvcutter.application.services.startup_recovery_service.StartupRecoveryService.recover_job_state",
        _raise,
    )
    bootstrap = AppBootstrap(
        checker=_SupportedChecker(),
        repositories=repo,
        runtime_path=str(tmp_path),
    )
    launch_result = bootstrap.launch()
    assert launch_result["status"] == "blocked"
    assert launch_result["reason"] == "startup_recovery_failed"


def test_launch_blocks_when_confirmation_required_after_recovery(tmp_path: Path) -> None:
    # Ensure deterministic policy path regardless of host disk state.
    from cvcutter import app as app_module
    from cvcutter.application.services.storage_safety_service import StoragePolicyDecision

    original = app_module.evaluate_storage_policy_for_path
    app_module.evaluate_storage_policy_for_path = lambda *_args, **_kwargs: (
        25,
        StoragePolicyDecision(
            policy="confirmation_required",
            event_type="storage.confirmation_required",
            payload={"free_gb": 25},
        ),
    )
    bootstrap = AppBootstrap(
        checker=_RecoveredChecker(),
        runtime_path=str(tmp_path),
    )
    try:
        launch_result = bootstrap.launch()
        assert launch_result["status"] == "blocked"
        assert "storage_confirmation_required" in str(launch_result["reason"])
    finally:
        app_module.evaluate_storage_policy_for_path = original


def test_launch_blocks_when_storage_probe_fails(tmp_path: Path) -> None:
    from cvcutter import app as app_module

    def _raise_probe_error(*_args, **_kwargs):
        raise OSError("probe failed")

    original = app_module.evaluate_storage_policy_for_path
    app_module.evaluate_storage_policy_for_path = _raise_probe_error
    bootstrap = AppBootstrap(
        checker=_SupportedChecker(),
        runtime_path=str(tmp_path),
    )
    try:
        launch_result = bootstrap.launch()
        assert launch_result["status"] == "blocked"
        assert launch_result["reason"] == "storage_probe_failed"
    finally:
        app_module.evaluate_storage_policy_for_path = original
