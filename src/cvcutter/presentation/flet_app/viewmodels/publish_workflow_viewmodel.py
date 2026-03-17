from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PublishWorkflowViewModel:
    consent_given: bool = False

    def can_save_plaintext_credentials(self) -> bool:
        return self.consent_given
