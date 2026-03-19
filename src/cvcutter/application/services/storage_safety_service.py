from __future__ import annotations

import shutil
from pathlib import Path


def evaluate_storage_policy(
    free_gb: int,
    *,
    recovered_from_block: bool = False,
    operator_confirmed: bool = False,
) -> str:
    if free_gb < 5:
        return "safe_pause"
    if free_gb < 10:
        return "start_blocked"
    if recovered_from_block and not operator_confirmed:
        return "confirmation_required"
    if free_gb < 20:
        return "warning"
    return "ok"


def read_free_gb(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return int(usage.free // (1024**3))


def evaluate_storage_policy_for_path(
    path: Path,
    *,
    recovered_from_block: bool = False,
    operator_confirmed: bool = False,
) -> tuple[int, str]:
    free_gb = read_free_gb(path)
    policy = evaluate_storage_policy(
        free_gb,
        recovered_from_block=recovered_from_block,
        operator_confirmed=operator_confirmed,
    )
    return free_gb, policy
