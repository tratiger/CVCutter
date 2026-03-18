import sqlite3
from pathlib import Path

import pytest

from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


def test_publish_key_uniqueness(sqlite_repo) -> None:
    sqlite_repo.store_publish_key("k1", "job")
    with pytest.raises(sqlite3.IntegrityError):
        sqlite_repo.store_publish_key("k1", "job")


def test_active_job_lock_uniqueness(sqlite_repo) -> None:
    assert sqlite_repo.acquire_active_job_lock("job-a")
    assert not sqlite_repo.acquire_active_job_lock("job-b")


def test_draft_lock_uniqueness(sqlite_repo) -> None:
    assert sqlite_repo.acquire_draft_lock("draft-1")
    assert not sqlite_repo.acquire_draft_lock("draft-1")


def test_checkpoint_uniqueness_uses_job_stage_attempt(sqlite_repo) -> None:
    sqlite_repo.insert_checkpoint("job-1", "ingest", 1, "completed")
    sqlite_repo.insert_checkpoint("job-1", "ingest", 2, "completed")
    with pytest.raises(sqlite3.IntegrityError):
        sqlite_repo.insert_checkpoint("job-1", "ingest", 1, "completed")


def test_required_schema_tables_exist(sqlite_repo) -> None:
    conn = sqlite_repo.connect()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN "
            "('segments', 'audio_source_profiles', 'metadata_mapping', 'role_policy')"
        ).fetchall()
    finally:
        conn.close()
    assert {row[0] for row in rows} == {
        "segments",
        "audio_source_profiles",
        "metadata_mapping",
        "role_policy",
    }


def test_checkpoint_legacy_schema_is_migrated(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    legacy_conn = sqlite3.connect(db_path)
    try:
        legacy_conn.executescript(
            """
            CREATE TABLE checkpoints (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO checkpoints(id, job_id, stage, status, created_at) VALUES
                ('legacy-1', 'job-legacy', 'ingest', 'completed', '2024-01-01T00:00:00Z'),
                ('legacy-2', 'job-legacy', 'ingest', 'failed', '2024-01-01T00:00:01Z');
            """
        )
        legacy_conn.commit()
    finally:
        legacy_conn.close()

    repo = SqliteRepositories(db_path)
    repo.init_schema()
    repo.insert_checkpoint("job-legacy", "ingest", 3, "completed")

    assert repo.list_checkpoints("job-legacy") == [
        ("ingest", 1, "completed"),
        ("ingest", 2, "failed"),
        ("ingest", 3, "completed"),
    ]
