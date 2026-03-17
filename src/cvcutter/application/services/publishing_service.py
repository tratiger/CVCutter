from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


@dataclass(slots=True)
class PublishResult:
    status: str
    event_type: str


class PublishingService:
    def __init__(self, repositories: SqliteRepositories, job_id: str = "job") -> None:
        self.repositories = repositories
        self.job_id = job_id

    def publish(self, dedup_key: str) -> PublishResult:
        try:
            self.repositories.store_publish_key(dedup_key, self.job_id)
        except sqlite3.IntegrityError:
            return PublishResult("blocked", "publish.dedup_blocked")
        return PublishResult("published", "publish.completed")
