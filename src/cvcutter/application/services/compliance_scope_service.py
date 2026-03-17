from __future__ import annotations


def verify_scope(feature_flags: set[str]) -> bool:
    forbidden = {"mobile_ui", "distributed_cloud"}
    return forbidden.isdisjoint(feature_flags)
