import sqlite3

import pytest


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
