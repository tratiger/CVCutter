from __future__ import annotations

import platform


class PlatformCompatibilityChecker:
    def ensure_supported(self) -> dict[str, str | bool]:
        system = platform.system().lower()
        if system not in {"windows", "darwin"}:
            return {"supported": False, "reason": "unsupported_os"}
        return {"supported": True, "reason": "ok"}
