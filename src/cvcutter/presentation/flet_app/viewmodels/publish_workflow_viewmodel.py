from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PublishWorkflowViewModel:
    consent_given: bool = False
    _plaintext_credentials: dict[str, str] = field(default_factory=dict)

    def can_save_plaintext_credentials(self) -> bool:
        return self.consent_given

    def save_plaintext_credentials(self, credentials: dict[str, str]) -> bool:
        if not self.can_save_plaintext_credentials():
            return False
        self._plaintext_credentials = dict(credentials)
        return True

    def load_plaintext_credentials(self) -> dict[str, str]:
        return dict(self._plaintext_credentials)
