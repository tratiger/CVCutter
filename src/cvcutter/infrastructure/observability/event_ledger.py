from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class EventLedger:
    path: Path

    @contextmanager
    def _cross_process_lock(self):
        lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock_file:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    import msvcrt

                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def append(self, event_type: str, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = (
            json.dumps({"event_type": event_type, "payload": payload}, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        with self._cross_process_lock():
            file_descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY)
            try:
                written_total = 0
                while written_total < len(line):
                    written = os.write(file_descriptor, line[written_total:])
                    if written <= 0:
                        raise OSError("failed to write event ledger entry")
                    written_total += written
            finally:
                os.close(file_descriptor)

    def reject_mutation(self) -> None:
        raise PermissionError("append-only ledger")
