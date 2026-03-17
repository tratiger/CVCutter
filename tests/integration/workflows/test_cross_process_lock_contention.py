from pathlib import Path

from cvcutter.application.services.lock_service import LockService
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


def test_lock_contention_and_release(tmp_path: Path) -> None:
    db_path = tmp_path / "locks.db"
    first_repo = SqliteRepositories(db_path)
    second_repo = SqliteRepositories(db_path)
    first_repo.init_schema()
    second_repo.init_schema()
    first = LockService(repositories=first_repo)
    second = LockService(repositories=second_repo)
    assert first.acquire_active_job("a")
    assert not second.acquire_active_job("b")
    first.release_active_job("a")
    assert second.acquire_active_job("b")


def test_draft_lock_cannot_be_released_by_non_owner(tmp_path: Path) -> None:
    db_path = tmp_path / "locks.db"
    owner_repo = SqliteRepositories(db_path)
    other_repo = SqliteRepositories(db_path)
    owner_repo.init_schema()
    other_repo.init_schema()
    owner_service = LockService(repositories=owner_repo)
    other_service = LockService(repositories=other_repo)

    assert owner_service.acquire_draft("draft-1", owner="owner-a")
    other_service.release_draft("draft-1", owner="owner-b")
    assert not other_service.acquire_draft("draft-1", owner="owner-b")
    owner_service.release_draft("draft-1", owner="owner-a")
    assert other_service.acquire_draft("draft-1", owner="owner-b")
