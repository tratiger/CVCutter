from __future__ import annotations


from __future__ import annotations

from dataclasses import dataclass

from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


def detect_stale_state(last_heartbeat_seconds: int, threshold_seconds: int = 300) -> bool:
    return last_heartbeat_seconds > threshold_seconds


def can_start_new_job(has_stale_lock: bool) -> bool:
    return not has_stale_lock


def recover_startup_state(
    *,
    current_state: str,
    last_heartbeat_seconds: int,
    worker_alive: bool,
) -> dict[str, object]:
    transitions: list[str] = []
    if current_state == "running" and detect_stale_state(last_heartbeat_seconds) and not worker_alive:
        transitions.append("paused")
        transitions.append("resumable")
        return {"state": "resumable", "transitions": transitions}
    return {"state": current_state, "transitions": transitions}


@dataclass(slots=True)
class StartupRecoveryService:
    repositories: SqliteRepositories

    def recover_job_state(
        self,
        *,
        job_id: str,
        last_heartbeat_seconds: int,
        worker_alive: bool,
    ) -> dict[str, object]:
        current_state = self.repositories.get_job_state(job_id)
        if current_state is None:
            raise RuntimeError("job_not_found")
        result = recover_startup_state(
            current_state=current_state,
            last_heartbeat_seconds=last_heartbeat_seconds,
            worker_alive=worker_alive,
        )
        new_state = str(result["state"])
        if new_state != current_state:
            self.repositories.update_job_state(job_id, new_state)
        return result
