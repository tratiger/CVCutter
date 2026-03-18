from __future__ import annotations


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
