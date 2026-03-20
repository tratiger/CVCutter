from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from cvcutter.infrastructure.packaging.platform_compatibility import PlatformCompatibilityChecker
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories
from cvcutter.application.services.startup_recovery_service import StartupRecoveryService
from cvcutter.application.services.storage_safety_service import evaluate_storage_policy_for_path
from cvcutter.presentation.flet_app.views.onboarding_view import OnboardingView


def _is_truthy(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _should_treat_worker_alive(
    lock_info: tuple[str, int] | None,
    *,
    job_id: str,
    stale_threshold_seconds: int = 300,
) -> bool:
    if lock_info is None:
        return False
    owner, heartbeat_age = lock_info
    return owner == job_id and heartbeat_age <= stale_threshold_seconds


@dataclass(slots=True)
class AppBootstrap:
    checker: PlatformCompatibilityChecker
    repositories: SqliteRepositories | None = None
    runtime_path: str = "."

    def launch(self) -> dict[str, str | bool]:
        result = self.checker.ensure_supported()
        if not result["supported"]:
            return {"status": "blocked", "reason": result["reason"]}
        if self.repositories is not None:
            try:
                recovery = StartupRecoveryService(self.repositories)
                lock_info = self.repositories.get_active_job_lock_info()
                for job_id in self.repositories.list_jobs_by_state("running"):
                    if _should_treat_worker_alive(lock_info, job_id=job_id):
                        if lock_info is None:
                            heartbeat_age = 0
                        else:
                            heartbeat_age = lock_info[1]
                        worker_alive = True
                    else:
                        heartbeat_age = 600
                        worker_alive = False
                    recovery.recover_job_state(
                        job_id=job_id,
                        last_heartbeat_seconds=heartbeat_age,
                        worker_alive=worker_alive,
                    )
            except (OSError, RuntimeError, sqlite3.Error):
                return {"status": "blocked", "reason": "startup_recovery_failed"}
        recovered_from_block = _is_truthy(result.get("recovered_from_block"))
        operator_confirmed = _is_truthy(result.get("operator_confirmed"))
        try:
            free_gb, storage_policy = evaluate_storage_policy_for_path(
                Path(self.runtime_path),
                recovered_from_block=recovered_from_block,
                operator_confirmed=operator_confirmed,
            )
        except OSError:
            return {"status": "blocked", "reason": "storage_probe_failed"}
        if storage_policy.policy in {"start_blocked", "safe_pause", "confirmation_required"}:
            return {"status": "blocked", "reason": f"storage_{storage_policy.policy}_{free_gb}gb"}
        return {"status": "ready", "next": OnboardingView().first_draft_hint()}


def run_runtime(bootstrap: AppBootstrap) -> int:
    launch_result = bootstrap.launch()
    if launch_result["status"] != "ready":
        return 1
    OnboardingView().run()
    return 0


def main() -> int:
    bootstrap = AppBootstrap(checker=PlatformCompatibilityChecker())
    return run_runtime(bootstrap)


if __name__ == "__main__":
    raise SystemExit(main())
