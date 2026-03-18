from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4


def _default_credentials_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "CVCutter" / "plaintext-credentials.json"
    return Path.home() / ".config" / "cvcutter" / "plaintext-credentials.json"


@dataclass(slots=True)
class PublishWorkflowViewModel:
    consent_given: bool = False
    credentials_path: Path = field(default_factory=_default_credentials_path)

    def can_save_plaintext_credentials(self) -> bool:
        return self.consent_given

    def save_plaintext_credentials(self, credentials: dict[str, str]) -> bool:
        if not self.can_save_plaintext_credentials():
            return False
        serialized = {str(key): str(value) for key, value in credentials.items()}
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.credentials_path.with_suffix(f"{self.credentials_path.suffix}.{uuid4().hex}.tmp")
        try:
            temp_path.write_text(
                json.dumps(serialized, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_path.replace(self.credentials_path)
        except OSError as error:
            raise RuntimeError("plaintext_credential_write_failed") from error
        return True

    def load_plaintext_credentials(self) -> dict[str, str]:
        if not self.credentials_path.exists():
            return {}
        try:
            payload = json.loads(self.credentials_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("invalid_plaintext_credential_payload") from error
        except OSError as error:
            raise RuntimeError("plaintext_credential_read_failed") from error
        if not isinstance(payload, dict):
            raise ValueError("invalid_plaintext_credential_payload")
        normalized: dict[str, str] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("invalid_plaintext_credential_payload")
            normalized[key] = value
        return normalized
