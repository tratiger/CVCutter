from __future__ import annotations


PROTECTED_PREFIX = "audit:"


def cleanup_artifact(name: str) -> tuple[bool, str]:
    if name.startswith(PROTECTED_PREFIX):
        return False, "protected_audit"
    return True, "deleted"
