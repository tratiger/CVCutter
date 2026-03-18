from __future__ import annotations

from dataclasses import dataclass


PROTECTED_PREFIX = "audit:"


@dataclass(slots=True)
class CleanupOutcome:
    event_type: str
    actor_role: str
    target_class: str
    target_id: str
    outcome: str
    reason: str


def cleanup_artifact(name: str, *, actor_role: str = "operator") -> CleanupOutcome:
    if name.startswith(PROTECTED_PREFIX):
        return CleanupOutcome(
            event_type="cleanup.rejected",
            actor_role=actor_role,
            target_class="protected_minimal_audit",
            target_id=name,
            outcome="rejected",
            reason="policy_protected",
        )
    return CleanupOutcome(
        event_type="cleanup.performed",
        actor_role=actor_role,
        target_class="deletable_artifact",
        target_id=name,
        outcome="performed",
        reason="user_requested",
    )
