from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class StoragePolicyDecision:
    policy: str
    event_type: str
    payload: dict[str, object]


def _build_storage_decision(free_gb: int, policy: str) -> StoragePolicyDecision:
    threshold_map = {"warning": 20, "start_blocked": 10, "safe_pause": 5}
    event_map = {
        "warning": "storage.threshold_warning",
        "start_blocked": "storage.threshold_block",
        "safe_pause": "storage.threshold_pause",
    }
    action_map = {
        "warning": "warn_and_continue",
        "start_blocked": "block_new_starts",
        "safe_pause": "pause_active_job",
    }
    if policy not in event_map:
        return StoragePolicyDecision(policy=policy, event_type="storage.ok", payload={"free_gb": free_gb})
    return StoragePolicyDecision(
        policy=policy,
        event_type=event_map[policy],
        payload={
            "free_gb": free_gb,
            "threshold_gb": threshold_map[policy],
            "action_taken": action_map[policy],
        },
    )


def evaluate_storage_policy(
    free_gb: int,
    *,
    recovered_from_block: bool = False,
    operator_confirmed: bool = False,
) -> StoragePolicyDecision:
    if free_gb < 5:
        return _build_storage_decision(free_gb, "safe_pause")
    if free_gb < 10:
        return _build_storage_decision(free_gb, "start_blocked")
    if recovered_from_block and not operator_confirmed:
        return StoragePolicyDecision(
            policy="confirmation_required",
            event_type="storage.confirmation_required",
            payload={"free_gb": free_gb, "threshold_gb": 10, "action_taken": "require_operator_confirmation"},
        )
    if free_gb < 20:
        return _build_storage_decision(free_gb, "warning")
    return StoragePolicyDecision(policy="ok", event_type="storage.ok", payload={"free_gb": free_gb})


def read_free_gb(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return int(usage.free // (1024**3))


def evaluate_storage_policy_for_path(
    path: Path,
    *,
    recovered_from_block: bool = False,
    operator_confirmed: bool = False,
) -> tuple[int, StoragePolicyDecision]:
    free_gb = read_free_gb(path)
    decision = evaluate_storage_policy(
        free_gb,
        recovered_from_block=recovered_from_block,
        operator_confirmed=operator_confirmed,
    )
    return free_gb, decision
