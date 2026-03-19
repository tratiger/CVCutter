from __future__ import annotations

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
            recovery = StartupRecoveryService(self.repositories)
            active_owner = self.repositories.get_active_job_lock_owner()
            for job_id in self.repositories.list_jobs_by_state("running"):
                recovery.recover_job_state(
                    job_id=job_id,
                    last_heartbeat_seconds=600,
                    worker_alive=(active_owner == job_id),
                )
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
        if storage_policy in {"start_blocked", "safe_pause", "confirmation_required"}:
            return {"status": "blocked", "reason": f"storage_{storage_policy}_{free_gb}gb"}
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
