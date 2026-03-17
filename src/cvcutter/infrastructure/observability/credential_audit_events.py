from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cvcutter.infrastructure.observability.event_ledger import EventLedger


@dataclass(slots=True)
class CredentialAuditEvents:
    path: Path

    def record(self, source: str, consent: bool) -> None:
        ledger = EventLedger(self.path)
        ledger.append("credential.consent_recorded", {"source": source, "consent": consent})
