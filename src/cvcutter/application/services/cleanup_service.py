from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


PROTECTED_PREFIX = "audit:"


@dataclass(slots=True)
class CleanupOutcome:
    event_type: str
    actor_role: str
    target_class: str
    target_id: str
    outcome: str
    reason: str


def _resolve_artifact_path(name: str, managed_root: Path) -> Path | None:
    if not name.strip():
        return None

    requested = Path(name)
    candidate = requested.resolve() if requested.is_absolute() else (managed_root / requested).resolve()
    if candidate == managed_root:
        return None
    try:
        candidate.relative_to(managed_root)
    except ValueError:
        return None
    return candidate


def cleanup_artifact(
    name: str,
    *,
    actor_role: str = "operator",
    managed_root: Path | None = None,
) -> CleanupOutcome:
    if name.startswith(PROTECTED_PREFIX):
        return CleanupOutcome(
            event_type="cleanup.rejected",
            actor_role=actor_role,
            target_class="protected_minimal_audit",
            target_id=name,
            outcome="rejected",
            reason="policy_protected",
        )
    if managed_root is None:
        return CleanupOutcome(
            event_type="cleanup.rejected",
            actor_role=actor_role,
            target_class="deletable_artifact",
            target_id=name,
            outcome="rejected",
            reason="policy_protected",
        )
    root = managed_root.resolve()
    artifact_path = _resolve_artifact_path(name, root)
    if artifact_path is None:
        return CleanupOutcome(
            event_type="cleanup.rejected",
            actor_role=actor_role,
            target_class="deletable_artifact",
            target_id=name,
            outcome="rejected",
            reason="policy_protected",
        )
    if artifact_path.exists():
        try:
            if artifact_path.is_dir():
                shutil.rmtree(artifact_path)
            else:
                artifact_path.unlink()
        except OSError:
            return CleanupOutcome(
                event_type="cleanup.rejected",
                actor_role=actor_role,
                target_class="deletable_artifact",
                target_id=name,
                outcome="rejected",
                reason="delete_failed",
            )
    return CleanupOutcome(
        event_type="cleanup.performed",
        actor_role=actor_role,
        target_class="deletable_artifact",
        target_id=name,
        outcome="performed",
        reason="user_requested",
    )
