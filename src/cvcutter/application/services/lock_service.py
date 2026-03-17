from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


@dataclass(slots=True)
class LockService:
    repositories: SqliteRepositories

    @classmethod
    def for_database(cls, db_path: Path) -> LockService:
        repositories = SqliteRepositories(db_path)
        repositories.init_schema()
        return cls(repositories=repositories)

    def acquire_active_job(self, job_id: str) -> bool:
        return self.repositories.acquire_active_job_lock(job_id)

    def release_active_job(self, job_id: str) -> None:
        self.repositories.release_active_job_lock(job_id)

    def acquire_draft(self, draft_id: str, owner: str = "operator") -> bool:
        return self.repositories.acquire_draft_lock(draft_id, owner)

    def release_draft(self, draft_id: str, owner: str = "operator") -> None:
        self.repositories.release_draft_lock(draft_id, owner)
