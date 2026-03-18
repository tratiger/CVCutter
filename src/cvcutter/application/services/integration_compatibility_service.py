from __future__ import annotations


def check_compatibility(
    provider: str,
    actual_version: str,
    pinned_versions: dict[str, str],
) -> dict[str, str | bool]:
    pinned = pinned_versions.get(provider)
    if pinned is None:
        return {"compatible": False, "reason": "missing_pinned_version", "guidance": "set_provider_pin"}
    if pinned != actual_version:
        return {
            "compatible": False,
            "reason": "pinned_version_mismatch",
            "guidance": "update_provider_or_pin",
        }
    return {"compatible": True, "reason": "ok", "guidance": "none"}
