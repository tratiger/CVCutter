from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


REQUIRED_CHECKPOINT_COLUMNS = {"checkpoint_id", "job_id", "stage_name", "attempt", "status"}


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
            self._migrate_legacy_checkpoints(conn)
            conn.commit()
        finally:
            conn.close()

    def _migrate_legacy_checkpoints(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(checkpoints)").fetchall()
        if not rows:
            return

        columns = {str(row[1]) for row in rows}
        if REQUIRED_CHECKPOINT_COLUMNS.issubset(columns):
            return

        if not {"job_id", "status"}.issubset(columns):
            raise RuntimeError("unsupported_checkpoint_schema")

        if "stage_name" in columns:
            stage_column = "stage_name"
        elif "stage" in columns:
            stage_column = "stage"
        else:
            raise RuntimeError("unsupported_checkpoint_schema")

        id_expression = "checkpoint_id"
        if "checkpoint_id" in columns:
            id_expression = "checkpoint_id"
        elif "id" in columns:
            id_expression = "id"
        else:
            id_expression = "lower(hex(randomblob(16)))"

        created_at_expression = "created_at" if "created_at" in columns else "CURRENT_TIMESTAMP"

        conn.execute("ALTER TABLE checkpoints RENAME TO checkpoints_legacy")
        conn.execute(
            """
            CREATE TABLE checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(job_id, stage_name, attempt)
            )
            """
        )
        conn.execute(
            "INSERT INTO checkpoints(checkpoint_id, job_id, stage_name, attempt, status, created_at) "
            f"SELECT {id_expression}, job_id, {stage_column}, "
            f"ROW_NUMBER() OVER (PARTITION BY job_id, {stage_column} ORDER BY {created_at_expression}, rowid), "
            f"status, {created_at_expression} "
            "FROM checkpoints_legacy"
        )
        conn.execute("DROP TABLE checkpoints_legacy")

    def insert_job(self, job_id: str, state: str, role: str) -> None:
        self._execute_write(
            "INSERT INTO jobs(job_id, state, role) VALUES (?, ?, ?)",
            (job_id, state, role),
        )

    def insert_checkpoint(self, job_id: str, stage_name: str, attempt: int, status: str) -> None:
        self._execute_write(
            "INSERT INTO checkpoints(checkpoint_id, job_id, stage_name, attempt, status) VALUES (?, ?, ?, ?, ?)",
            (str(uuid4()), job_id, stage_name, attempt, status),
        )

    def list_checkpoints(self, job_id: str) -> list[tuple[str, int, str]]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT stage_name, attempt, status FROM checkpoints WHERE job_id = ? ORDER BY attempt, stage_name",
                (job_id,),
            ).fetchall()
        finally:
            conn.close()
        return [(str(row[0]), int(row[1]), str(row[2])) for row in rows]

    def save_classification_strategy(self, job_id: str, strategy: str) -> None:
        self._execute_write(
            "INSERT INTO classification_strategies(job_id, strategy) VALUES (?, ?) "
            "ON CONFLICT(job_id) DO UPDATE SET strategy = excluded.strategy, updated_at = CURRENT_TIMESTAMP",
            (job_id, strategy),
        )

    def load_classification_strategy(self, job_id: str) -> str | None:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT strategy FROM classification_strategies WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return str(row[0])

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
