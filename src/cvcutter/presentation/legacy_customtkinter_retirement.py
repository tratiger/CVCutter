from __future__ import annotations

RETIRED_ENTRYPOINTS = [
    "customtkinter.App",
    "legacy preview/upload tabs",
]


def migration_complete() -> bool:
    return True
