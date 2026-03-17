from __future__ import annotations


EXECUTABLE_ROLE = "operator"


def enforce_executable_role(role: str) -> None:
    if role != EXECUTABLE_ROLE:
        raise PermissionError(f"Only {EXECUTABLE_ROLE} can execute workflows.")
