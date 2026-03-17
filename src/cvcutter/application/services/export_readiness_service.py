from __future__ import annotations


def export_ready(unresolved_reviews: int, unresolved_sync_flags: int) -> bool:
    return unresolved_reviews == 0 and unresolved_sync_flags == 0
