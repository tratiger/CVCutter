import sqlite3
from pathlib import Path

import pytest

from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


def test_publish_key_uniqueness(sqlite_repo) -> None:
    sqlite_repo.store_publish_key("job-a", "segment-1", "youtube")
    with pytest.raises(sqlite3.IntegrityError):
        sqlite_repo.store_publish_key("job-a", "segment-1", "youtube")
    sqlite_repo.store_publish_key("job-b", "segment-1", "youtube")
    sqlite_repo.store_publish_key("job-a", "segment-1", "youtube-alt")


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


def test_publish_key_legacy_schema_is_migrated(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-publish.db"
    legacy_conn = sqlite3.connect(db_path)
    try:
        legacy_conn.executescript(
            """
            CREATE TABLE publish_keys (
                key TEXT PRIMARY KEY,
                job_id TEXT NOT NULL
            );
            INSERT INTO publish_keys(key, job_id)
            VALUES ('segment-legacy', 'job-legacy');
            """
        )
        legacy_conn.commit()
    finally:
        legacy_conn.close()

    repo = SqliteRepositories(db_path)
    repo.init_schema()

    with pytest.raises(sqlite3.IntegrityError):
        repo.store_publish_key("job-legacy", "segment-legacy", "youtube")
    repo.store_publish_key("job-another", "segment-legacy", "youtube")


def test_persistence_crud_for_segments_audio_mapping_role_events_and_config(sqlite_repo) -> None:
    sqlite_repo.insert_segment("seg-1", "job-1", 100, 500, 82, "pending")
    sqlite_repo.insert_audio_source_profile(
        "audio-1",
        "job-1",
        "main",
        "embedded_video",
        0,
        1.5,
        0.2,
        "simple",
        "ok",
        "not_required",
    )
    sqlite_repo.insert_metadata_mapping(
        "map-1",
        "job-1",
        "seg-1",
        "2",
        "Track 1",
        "desc",
        ["concert", "live"],
        {"source": "catalog"},
        "public",
        "valid",
    )
    sqlite_repo.insert_role_policy("role-1", "job-1", "operator", "editor,publisher")
    sqlite_repo.append_event("job.created", "job-1", '{"state":"running"}')
    sqlite_repo.record_config_change("job-1", "classification_strategy")

    assert sqlite_repo.list_segments("job-1") == [("seg-1", 100, 500, 82, "pending")]
    assert sqlite_repo.list_audio_source_profiles("job-1") == [
        ("audio-1", "main", "embedded_video", 0, 1.5, 0.2, "simple", "ok", "not_required")
    ]
    assert sqlite_repo.list_metadata_mappings("job-1") == [
        ("map-1", "seg-1", "2", "Track 1", ["concert", "live"], {"source": "catalog"}, "public", "valid")
    ]
    assert sqlite_repo.list_role_policies("job-1") == [("role-1", "operator", "editor,publisher")]
    assert sqlite_repo.list_events("job-1") == [("job.created", "job-1", '{"state":"running"}')]
    assert sqlite_repo.list_config_changes("job-1") == ["classification_strategy"]


def test_upsert_job_updates_state_and_role(sqlite_repo) -> None:
    sqlite_repo.insert_job("job-1", "draft", "operator")
    sqlite_repo.upsert_job("job-1", "running", "operator")
    assert sqlite_repo.get_job_state("job-1") == "running"


def test_get_active_job_lock_owner(sqlite_repo) -> None:
    assert sqlite_repo.get_active_job_lock_owner() is None
    assert sqlite_repo.acquire_active_job_lock("job-1")
    assert sqlite_repo.get_active_job_lock_owner() == "job-1"


def test_get_active_job_lock_info(sqlite_repo) -> None:
    assert sqlite_repo.get_active_job_lock_info() is None
    assert sqlite_repo.acquire_active_job_lock("job-1")
    lock_info = sqlite_repo.get_active_job_lock_info()
    assert lock_info is not None
    owner, heartbeat_age = lock_info
    assert owner == "job-1"
    assert heartbeat_age >= 0


def test_locks_legacy_schema_is_migrated_with_heartbeat(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-locks.db"
    legacy_conn = sqlite3.connect(db_path)
    try:
        legacy_conn.executescript(
            """
            CREATE TABLE locks (
                lock_name TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                state TEXT NOT NULL
            );
            INSERT INTO locks(lock_name, owner, state)
            VALUES ('active_job', 'job-legacy', 'active');
            """
        )
        legacy_conn.commit()
    finally:
        legacy_conn.close()

    repo = SqliteRepositories(db_path)
    repo.init_schema()
    lock_info = repo.get_active_job_lock_info()
    assert lock_info is not None
    owner, heartbeat_age = lock_info
    assert owner == "job-legacy"
    assert heartbeat_age >= 300
