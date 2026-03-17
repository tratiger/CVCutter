from pathlib import Path

from cvcutter.application.services.publishing_service import PublishingService
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


def test_publish_dedup_blocked_event(tmp_path: Path) -> None:
    db_path = tmp_path / "publish.db"
    first_repo = SqliteRepositories(db_path)
    second_repo = SqliteRepositories(db_path)
    first_repo.init_schema()
    second_repo.init_schema()
    first_service = PublishingService(first_repo, job_id="job")
    second_service = PublishingService(second_repo, job_id="job")
    first = first_service.publish("k")
    second = second_service.publish("k")
    assert first.status == "published"
    assert second.event_type == "publish.dedup_blocked"
