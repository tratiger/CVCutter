from __future__ import annotations

from cvcutter.application.services.cleanup_service import cleanup_artifact


class CleanupController:
    def request_cleanup(self, name: str, *, actor_role: str = "operator") -> dict[str, str]:
        outcome = cleanup_artifact(name, actor_role=actor_role)
        return {
            "event_type": outcome.event_type,
            "actor_role": outcome.actor_role,
            "target_class": outcome.target_class,
            "target_id": outcome.target_id,
            "outcome": outcome.outcome,
            "reason": outcome.reason,
        }
