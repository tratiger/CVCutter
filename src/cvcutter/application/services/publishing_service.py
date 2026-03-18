from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


@dataclass(slots=True)
class PublishResult:
    status: str
    event_type: str


class PublishingService:
    def __init__(
        self,
        repositories: SqliteRepositories,
        job_id: str = "00000000-0000-0000-0000-000000000000",
    ) -> None:
        self.repositories = repositories
        self.job_id = job_id

    def publish(self, segment_id: str, destination: str = "youtube") -> PublishResult:
        try:
            self.repositories.store_publish_key(self.job_id, segment_id, destination)
        except sqlite3.IntegrityError:
            return PublishResult("blocked", "publish.dedup_blocked")
        return PublishResult("published", "publish.completed")
