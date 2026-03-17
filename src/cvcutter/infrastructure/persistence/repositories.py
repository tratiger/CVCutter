from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SqliteRepositories:
    db_path: Path
    timeout_seconds: float = 5.0

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=self.timeout_seconds)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _execute_write(self, sql: str, params: tuple[object, ...], retries: int = 3) -> None:
        last_error: sqlite3.OperationalError | None = None
        for _ in range(retries):
            try:
                conn = self.connect()
                try:
                    conn.execute(sql, params)
                    conn.commit()
                finally:
                    conn.close()
                return
            except sqlite3.OperationalError as error:
                if "locked" not in str(error).lower():
                    raise
                last_error = error
                time.sleep(0.05)
        if last_error is not None:
            raise last_error

    def init_schema(self) -> None:
        migration = Path(__file__).parent / "migrations" / "001_initial_schema.sql"
        sql = migration.read_text(encoding="utf-8")
        conn = self.connect()
        try:
            conn.executescript(sql)
            conn.commit()
        finally:
            conn.close()

    def insert_job(self, job_id: str, state: str, role: str) -> None:
        self._execute_write(
            "INSERT INTO jobs(job_id, state, role) VALUES (?, ?, ?)",
            (job_id, state, role),
        )

    def store_publish_key(self, key: str, job_id: str) -> None:
        self._execute_write(
            "INSERT INTO publish_keys(key, job_id) VALUES (?, ?)",
            (key, job_id),
        )

    def acquire_active_job_lock(self, job_id: str) -> bool:
        try:
            self._execute_write(
                "INSERT INTO locks(lock_name, owner, state) VALUES (?, ?, ?)",
                ("active_job", job_id, "active"),
            )
            return True
        except sqlite3.IntegrityError:
            conn = self.connect()
            try:
                row = conn.execute(
                    "SELECT owner FROM locks WHERE lock_name = ?",
                    ("active_job",),
                ).fetchone()
            finally:
                conn.close()
            return row is not None and row[0] == job_id

    def release_active_job_lock(self, job_id: str) -> None:
        self._execute_write(
            "DELETE FROM locks WHERE lock_name = ? AND owner = ?",
            ("active_job", job_id),
        )

    def acquire_draft_lock(self, draft_id: str, owner: str = "operator") -> bool:
        lock_name = f"draft:{draft_id}"
        try:
            self._execute_write(
                "INSERT INTO locks(lock_name, owner, state) VALUES (?, ?, ?)",
                (lock_name, owner, "active"),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def release_draft_lock(self, draft_id: str, owner: str = "operator") -> None:
        self._execute_write(
            "DELETE FROM locks WHERE lock_name = ? AND owner = ?",
            (f"draft:{draft_id}", owner),
        )
