import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

from cvcutter.infrastructure.observability.event_ledger import EventLedger


def test_mutation_deletion_guard_hardening(tmp_path: Path) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.append("event", {"a": 1})
    with pytest.raises(PermissionError):
        ledger.reject_mutation()


def _append_batch(path: str, count: int, start: int) -> None:
    ledger = EventLedger(Path(path))
    for index in range(count):
        ledger.append("event", {"value": start + index})


def test_event_ledger_append_is_concurrency_safe(tmp_path: Path) -> None:
    event_path = tmp_path / "events.jsonl"
    per_worker = 20
    workers = 4
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_append_batch, str(event_path), per_worker, worker_index * per_worker)
            for worker_index in range(workers)
        ]
        for future in futures:
            future.result()
    lines = event_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == per_worker * workers
    for line in lines:
        payload = json.loads(line)
        assert payload["event_type"] == "event"


def test_event_ledger_handles_partial_writes(tmp_path: Path, monkeypatch) -> None:
    event_path = tmp_path / "events.jsonl"
    ledger = EventLedger(event_path)
    original_write = os.write
    first_call = {"done": False}

    def _partial_write(file_descriptor: int, data: bytes) -> int:
        if not first_call["done"] and len(data) > 1:
            first_call["done"] = True
            half = max(1, len(data) // 2)
            original_write(file_descriptor, data[:half])
            return half
        return original_write(file_descriptor, data)

    monkeypatch.setattr(os, "write", _partial_write)
    ledger.append("event", {"value": 1})
    line = event_path.read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(line)["event_type"] == "event"
