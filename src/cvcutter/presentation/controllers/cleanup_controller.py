from __future__ import annotations

from cvcutter.application.services.cleanup_service import cleanup_artifact


class CleanupController:
    def request_cleanup(self, name: str) -> str:
        ok, message = cleanup_artifact(name)
        return "cleanup.completed" if ok else f"cleanup.rejected:{message}"
