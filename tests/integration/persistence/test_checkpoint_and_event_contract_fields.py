from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from cvcutter.application.dto.events import ProcessingEvent
from cvcutter.application.workflows.processing_workflow import ProcessingWorkflow
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


def test_checkpoint_schema_contains_resume_and_fingerprint_fields(sqlite_repo: SqliteRepositories) -> None:
    conn = sqlite_repo.connect()
    try:
        rows = conn.execute("PRAGMA table_info(checkpoints)").fetchall()
    finally:
        conn.close()
    columns = {str(row[1]) for row in rows}
    assert {"resume_cursor", "input_fingerprint", "output_fingerprint", "completed_at"}.issubset(columns)


def test_insert_and_list_checkpoint_preserves_extended_fields(sqlite_repo: SqliteRepositories) -> None:
    sqlite_repo.insert_checkpoint(
        "job-extended",
        "ingest",
        1,
        "completed",
        resume_cursor={"offset_ms": 1200},
        input_fingerprint="in-hash",
        output_fingerprint="out-hash",
        completed_at="2026-03-19T00:00:00Z",
    )
    checkpoints = sqlite_repo.list_checkpoints_detailed("job-extended")
    assert len(checkpoints) == 1
    checkpoint = checkpoints[0]
    assert checkpoint["stage_name"] == "ingest"
    assert checkpoint["attempt"] == 1
    assert checkpoint["status"] == "completed"
    assert checkpoint["resume_cursor"] == {"offset_ms": 1200}
    assert checkpoint["input_fingerprint"] == "in-hash"
    assert checkpoint["output_fingerprint"] == "out-hash"
    assert checkpoint["completed_at"] == "2026-03-19T00:00:00Z"


def test_processing_event_schema_contains_minimal_audit_flag(sqlite_repo: SqliteRepositories) -> None:
    conn = sqlite_repo.connect()
    try:
        rows = conn.execute("PRAGMA table_info(events)").fetchall()
    finally:
        conn.close()
    columns = {str(row[1]) for row in rows}
    assert "is_minimal_audit" in columns


def test_append_event_persists_minimal_audit_flag(sqlite_repo: SqliteRepositories) -> None:
    sqlite_repo.append_event(
        "job.created",
        "job-audit",
        '{"state":"running"}',
        is_minimal_audit=True,
    )
    sqlite_repo.append_event(
        "storage.threshold_warning",
        None,
        '{"free_gb":18,"threshold_gb":20,"action_taken":"warn"}',
        is_minimal_audit=False,
    )
    events = sqlite_repo.list_events_detailed()
    assert len(events) == 2
    assert events[0]["event_type"] == "job.created"
    assert events[0]["is_minimal_audit"] is True
    assert events[1]["event_type"] == "storage.threshold_warning"
    assert events[1]["is_minimal_audit"] is False


def test_migrate_legacy_checkpoint_and_event_schema_adds_contract_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-contract.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(job_id, stage_name, attempt)
            );

            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                job_id TEXT,
                payload TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    repo = SqliteRepositories(db_path)
    repo.init_schema()

    migrated = repo.connect()
    try:
        checkpoint_rows = migrated.execute("PRAGMA table_info(checkpoints)").fetchall()
        checkpoint_columns = {str(row[1]) for row in checkpoint_rows}
        event_columns = {str(row[1]) for row in migrated.execute("PRAGMA table_info(events)").fetchall()}
        checkpoint_meta = {str(row[1]): row for row in checkpoint_rows}
    finally:
        migrated.close()
    assert {"resume_cursor", "input_fingerprint", "output_fingerprint", "completed_at"}.issubset(
        checkpoint_columns
    )
    assert "is_minimal_audit" in event_columns
    assert int(checkpoint_meta["input_fingerprint"][3]) == 1


def test_migrate_checkpoint_schema_without_created_at_column_succeeds(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-no-created-at.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(job_id, stage_name, attempt)
            );
            INSERT INTO checkpoints(checkpoint_id, job_id, stage_name, attempt, status) VALUES
                ('cp-1', 'job-legacy', 'ingest', 1, 'completed');
            """
        )
        conn.commit()
    finally:
        conn.close()

    repo = SqliteRepositories(db_path)
    repo.init_schema()

    migrated_rows = repo.list_checkpoints_detailed("job-legacy")
    assert len(migrated_rows) == 1
    assert migrated_rows[0]["stage_name"] == "ingest"
    assert migrated_rows[0]["status"] == "completed"
    assert migrated_rows[0]["completed_at"] is not None


def test_workflow_persists_minimal_audit_for_stage_events(sqlite_repo: SqliteRepositories) -> None:
    workflow = ProcessingWorkflow(repositories=sqlite_repo)
    job = ProcessingJob("11111111-1111-1111-1111-111111111188")
    workflow.run_until_complete(job)

    persisted = sqlite_repo.list_events_detailed(job.job_id)
    assert persisted
    core_event_types = {"job.created", "job.state_changed", "stage.started", "stage.completed"}
    for row in persisted:
        if row["event_type"] in core_event_types:
            assert row["is_minimal_audit"] is True


def test_processing_event_payload_stays_json_when_roundtripped(sqlite_repo: SqliteRepositories) -> None:
    payload = {"next_action": "cleanup", "threshold_gb": 20}
    event = ProcessingEvent.new(
        event_type="storage.threshold_warning",
        job_id=None,
        payload=payload,
        severity="warning",
    )
    sqlite_repo.append_event(
        event.event_type,
        event.job_id,
        json.dumps(
            {
                "event_id": event.event_id,
                "event_schema_version": event.event_schema_version,
                "occurred_at": event.occurred_at,
                "stage_name": event.stage_name,
                "attempt": event.attempt,
                "severity": event.severity,
                "payload": event.payload,
            }
        ),
        is_minimal_audit=False,
    )
    rows = sqlite_repo.list_events()
    assert len(rows) == 1
    persisted_payload = json.loads(rows[0][2])
    assert persisted_payload["payload"] == payload
