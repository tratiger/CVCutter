"""JSON-backed adapter for credential persistence and redaction."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from cvcutter.domain.services.credential_store import CredentialStore


class JsonCredentialStore(CredentialStore):
    """Persist and load service credentials in per-user JSON files."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize the store with the per-user app data base directory."""
        self._base_dir = Path(base_dir)
        self._credentials_dir = self._base_dir / "credentials"

    def load(self, service_name: str) -> dict[str, str] | None:
        """Load credentials for a service name, returning None when unavailable."""
        credential_path = self._credential_path(service_name)
        try:
            payload = json.loads(credential_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return {str(key): str(value) for key, value in payload.items()}

    def save(self, service_name: str, credentials: dict[str, str]) -> None:
        """Persist credentials for a service and apply restricted file permissions."""
        credential_path = self._credential_path(service_name)
        try:
            credential_path.parent.mkdir(parents=True, exist_ok=True)
            credential_path.write_text(
                json.dumps(credentials, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError):
            return
        self._restrict_permissions(credential_path)

    def delete(self, service_name: str) -> None:
        """Delete credentials associated with a service name."""
        credential_path = self._credential_path(service_name)
        try:
            credential_path.unlink()
        except (FileNotFoundError, OSError):
            return

    def redacted_summary(self, service_name: str) -> dict[str, str]:
        """Return credential keys with redacted values for safe display."""
        credentials = self.load(service_name)
        if credentials is None:
            return {}
        return {key: "***" for key in credentials}

    def _credential_path(self, service_name: str) -> Path:
        """Build the credential JSON file path for a service."""
        safe_name = Path(service_name).name or "service"
        file_name = safe_name if safe_name.endswith(".json") else f"{safe_name}.json"
        return self._credentials_dir / file_name

    @staticmethod
    def _restrict_permissions(file_path: Path) -> None:
        """Apply best-effort owner-only read/write file permissions."""
        try:
            if os.name == "nt":
                os.chmod(file_path, stat.S_IREAD | stat.S_IWRITE)
            else:
                os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            return
