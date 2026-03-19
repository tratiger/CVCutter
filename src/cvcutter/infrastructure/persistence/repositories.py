from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
import json


REQUIRED_CHECKPOINT_COLUMNS = {"checkpoint_id", "job_id", "stage_name", "attempt", "status"}
REQUIRED_PUBLISH_KEY_COLUMNS = {"job_id", "segment_id", "destination"}


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
            self._migrate_legacy_publish_keys(conn)
            self._migrate_audio_source_profiles(conn)
            self._migrate_metadata_mapping(conn)
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

    def _migrate_legacy_publish_keys(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(publish_keys)").fetchall()
        if not rows:
            return

        columns = {str(row[1]) for row in rows}
        if REQUIRED_PUBLISH_KEY_COLUMNS.issubset(columns):
            return
        if not {"job_id", "key"}.issubset(columns):
            raise RuntimeError("unsupported_publish_keys_schema")

        conn.execute("ALTER TABLE publish_keys RENAME TO publish_keys_legacy")
        conn.execute(
            """
            CREATE TABLE publish_keys (
                job_id TEXT NOT NULL,
                segment_id TEXT NOT NULL,
                destination TEXT NOT NULL,
                PRIMARY KEY(job_id, segment_id, destination)
            )
            """
        )
        conn.execute(
            "INSERT INTO publish_keys(job_id, segment_id, destination) "
            "SELECT job_id, key, 'youtube' FROM publish_keys_legacy"
        )
        conn.execute("DROP TABLE publish_keys_legacy")

    def _migrate_audio_source_profiles(self, conn: sqlite3.Connection) -> None:
        columns = {
            str(row[1]): str(row[2]).upper()
            for row in conn.execute("PRAGMA table_info(audio_source_profiles)").fetchall()
        }
        if not columns:
            return
        if "gain_db" not in columns:
            conn.execute("ALTER TABLE audio_source_profiles ADD COLUMN gain_db REAL NOT NULL DEFAULT 0.0")
        if "noise_reduction_level" not in columns:
            conn.execute(
                "ALTER TABLE audio_source_profiles ADD COLUMN noise_reduction_level REAL NOT NULL DEFAULT 0.0"
            )
        if "tuning_mode" not in columns:
            conn.execute("ALTER TABLE audio_source_profiles ADD COLUMN tuning_mode TEXT NOT NULL DEFAULT 'simple'")

    def _migrate_metadata_mapping(self, conn: sqlite3.Connection) -> None:
        columns = {
            str(row[1]): str(row[2]).upper()
            for row in conn.execute("PRAGMA table_info(metadata_mapping)").fetchall()
        }
        if not columns:
            return
        if "tags" not in columns:
            conn.execute("ALTER TABLE metadata_mapping ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
        if "source_trace" not in columns:
            conn.execute("ALTER TABLE metadata_mapping ADD COLUMN source_trace TEXT NOT NULL DEFAULT '{}'")

    def insert_job(self, job_id: str, state: str, role: str) -> None:
        self._execute_write(
            "INSERT INTO jobs(job_id, state, role) VALUES (?, ?, ?)",
            (job_id, state, role),
        )

    def upsert_job(self, job_id: str, state: str, role: str) -> None:
        self._execute_write(
            "INSERT INTO jobs(job_id, state, role) VALUES (?, ?, ?) "
            "ON CONFLICT(job_id) DO UPDATE SET state = excluded.state, role = excluded.role",
            (job_id, state, role),
        )

    def get_job_state(self, job_id: str) -> str | None:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT state FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return str(row[0])

    def list_jobs_by_state(self, state: str) -> list[str]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT job_id FROM jobs WHERE state = ? ORDER BY job_id",
                (state,),
            ).fetchall()
        finally:
            conn.close()
        return [str(row[0]) for row in rows]

    def get_active_job_lock_owner(self) -> str | None:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT owner FROM locks WHERE lock_name = ? AND state = ?",
                ("active_job", "active"),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return str(row[0])

    def update_job_state(self, job_id: str, state: str) -> None:
        conn = self.connect()
        try:
            cursor = conn.execute(
                "UPDATE jobs SET state = ? WHERE job_id = ?",
                (state, job_id),
            )
            conn.commit()
        finally:
            conn.close()
        if cursor.rowcount == 0:
            raise RuntimeError("job_not_found")

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

    def store_publish_key(self, job_id: str, segment_id: str, destination: str) -> None:
        self._execute_write(
            "INSERT INTO publish_keys(job_id, segment_id, destination) VALUES (?, ?, ?)",
            (job_id, segment_id, destination),
        )

    def insert_segment(
        self,
        segment_id: str,
        job_id: str,
        start_ms: int,
        end_ms: int,
        confidence_score: int,
        review_status: str,
    ) -> None:
        self._execute_write(
            "INSERT INTO segments(segment_id, job_id, start_ms, end_ms, confidence_score, review_status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (segment_id, job_id, start_ms, end_ms, confidence_score, review_status),
        )

    def list_segments(self, job_id: str) -> list[tuple[str, int, int, int, str]]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT segment_id, start_ms, end_ms, confidence_score, review_status "
                "FROM segments WHERE job_id = ? ORDER BY start_ms",
                (job_id,),
            ).fetchall()
        finally:
            conn.close()
        return [
            (str(row[0]), int(row[1]), int(row[2]), int(row[3]), str(row[4]))
            for row in rows
        ]

    def insert_audio_source_profile(
        self,
        audio_profile_id: str,
        job_id: str,
        source_name: str,
        source_kind: str,
        offset_ms: int,
        gain_db: float,
        noise_reduction_level: float,
        tuning_mode: str,
        quality_status: str,
        correction_resolution_status: str,
    ) -> None:
        self._execute_write(
            "INSERT INTO audio_source_profiles("
            "audio_profile_id, job_id, source_name, source_kind, offset_ms, gain_db, noise_reduction_level, "
            "tuning_mode, quality_status, correction_resolution_status"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                audio_profile_id,
                job_id,
                source_name,
                source_kind,
                offset_ms,
                gain_db,
                noise_reduction_level,
                tuning_mode,
                quality_status,
                correction_resolution_status,
            ),
        )

    def list_audio_source_profiles(
        self,
        job_id: str,
    ) -> list[tuple[str, str, str, int, float, float, str, str, str]]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT audio_profile_id, source_name, source_kind, offset_ms, gain_db, noise_reduction_level, "
                "tuning_mode, quality_status, correction_resolution_status "
                "FROM audio_source_profiles WHERE job_id = ? ORDER BY audio_profile_id",
                (job_id,),
            ).fetchall()
        finally:
            conn.close()
        return [
            (
                str(row[0]),
                str(row[1]),
                str(row[2]),
                int(row[3]),
                float(row[4]),
                float(row[5]),
                str(row[6]),
                str(row[7]),
                str(row[8]),
            )
            for row in rows
        ]

    def insert_metadata_mapping(
        self,
        mapping_id: str,
        job_id: str,
        segment_id: str,
        schema_version: str,
        title: str,
        description: str,
        tags: list[str],
        source_trace: dict[str, object],
        publish_visibility: str,
        validation_status: str,
    ) -> None:
        self._execute_write(
            "INSERT INTO metadata_mapping("
            "mapping_id, job_id, segment_id, schema_version, title, description, tags, source_trace, "
            "publish_visibility, validation_status"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                mapping_id,
                job_id,
                segment_id,
                schema_version,
                title,
                description,
                json.dumps(tags, ensure_ascii=False),
                json.dumps(source_trace, ensure_ascii=False),
                publish_visibility,
                validation_status,
            ),
        )

    def list_metadata_mappings(
        self,
        job_id: str,
    ) -> list[tuple[str, str, str, str, list[str], dict[str, object], str, str]]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT mapping_id, segment_id, schema_version, title, tags, source_trace, publish_visibility, "
                "validation_status "
                "FROM metadata_mapping WHERE job_id = ? ORDER BY mapping_id",
                (job_id,),
            ).fetchall()
        finally:
            conn.close()
        return [
            (
                str(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                list(json.loads(str(row[4]))),
                dict(json.loads(str(row[5]))),
                str(row[6]),
                str(row[7]),
            )
            for row in rows
        ]

    def insert_role_policy(
        self,
        policy_id: str,
        job_id: str,
        executable_role: str,
        context_labels: str,
    ) -> None:
        self._execute_write(
            "INSERT INTO role_policy(policy_id, job_id, executable_role, context_labels) VALUES (?, ?, ?, ?)",
            (policy_id, job_id, executable_role, context_labels),
        )

    def list_role_policies(self, job_id: str) -> list[tuple[str, str, str]]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT policy_id, executable_role, context_labels FROM role_policy WHERE job_id = ? ORDER BY policy_id",
                (job_id,),
            ).fetchall()
        finally:
            conn.close()
        return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]

    def append_event(self, event_type: str, job_id: str | None, payload: str) -> None:
        self._execute_write(
            "INSERT INTO events(event_type, job_id, payload) VALUES (?, ?, ?)",
            (event_type, job_id, payload),
        )

    def list_events(self, job_id: str | None = None) -> list[tuple[str, str | None, str]]:
        conn = self.connect()
        try:
            if job_id is None:
                rows = conn.execute(
                    "SELECT event_type, job_id, payload FROM events ORDER BY id"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT event_type, job_id, payload FROM events WHERE job_id = ? ORDER BY id",
                    (job_id,),
                ).fetchall()
        finally:
            conn.close()
        return [
            (str(row[0]), None if row[1] is None else str(row[1]), str(row[2]))
            for row in rows
        ]

    def record_config_change(self, job_id: str, changed_key: str) -> None:
        self._execute_write(
            "INSERT INTO config_change_records(job_id, changed_key) VALUES (?, ?)",
            (job_id, changed_key),
        )

    def list_config_changes(self, job_id: str) -> list[str]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT changed_key FROM config_change_records WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        finally:
            conn.close()
        return [str(row[0]) for row in rows]

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
