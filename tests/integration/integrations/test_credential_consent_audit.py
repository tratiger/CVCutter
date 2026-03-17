import json
from pathlib import Path

from cvcutter.infrastructure.observability.credential_audit_events import CredentialAuditEvents


def test_credential_consent_audit_record(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    CredentialAuditEvents(path).record("plaintext", True)
    line = path.read_text(encoding="utf-8").strip().splitlines()[0]
    payload = json.loads(line)
    assert payload["event_type"] == "credential.consent_recorded"
