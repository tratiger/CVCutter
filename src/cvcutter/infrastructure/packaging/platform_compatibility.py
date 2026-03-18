from __future__ import annotations

import platform

_WINDOWS_ARCH = {"amd64", "x86_64", "arm64"}
_MAC_ARCH = {"x86_64", "arm64"}


class PlatformCompatibilityChecker:
    def ensure_supported(
        self,
        *,
        system: str | None = None,
        release: str | None = None,
        machine: str | None = None,
    ) -> dict[str, str | bool]:
        normalized_system = (system or platform.system()).strip().lower()
        normalized_machine = (machine or platform.machine()).strip().lower()

        if normalized_system == "windows":
            effective_release = (release or platform.release()).strip()
            if normalized_machine not in _WINDOWS_ARCH:
                return {"supported": False, "reason": "unsupported_architecture"}
            if not self._is_supported_windows_version(effective_release):
                return {"supported": False, "reason": "unsupported_windows_version"}
            return {"supported": True, "reason": "ok"}

        if normalized_system == "darwin":
            mac_release = (release or platform.mac_ver()[0]).strip()
            if normalized_machine not in _MAC_ARCH:
                return {"supported": False, "reason": "unsupported_architecture"}
            if not mac_release:
                return {"supported": False, "reason": "unsupported_macos_version"}
            if not self._is_supported_macos_version(mac_release):
                return {"supported": False, "reason": "unsupported_macos_version"}
            return {"supported": True, "reason": "ok"}

        return {"supported": False, "reason": "unsupported_os"}

    def _is_supported_windows_version(self, release: str) -> bool:
        major = self._parse_major(release)
        return major in {10, 11}

    def _is_supported_macos_version(self, release: str) -> bool:
        major = self._parse_major(release)
        if major >= 20:
            major -= 9
        return major >= 13

    def _parse_major(self, raw_version: str) -> int:
        token = raw_version.split(".", maxsplit=1)[0].strip()
        if token.isdigit():
            return int(token)
        return -1
