import pytest
from pathlib import Path

from cvcutter.infrastructure.observability.event_ledger import EventLedger


def test_event_ledger_append_only(tmp_path: Path) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.append("job.created", {"retry": {"attempt": 1}})
    with pytest.raises(PermissionError):
        ledger.reject_mutation()
