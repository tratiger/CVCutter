from pathlib import Path

from cvcutter.application.services.publishing_service import PublishingService
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


def test_publish_dedup_blocked_event(tmp_path: Path) -> None:
    db_path = tmp_path / "publish.db"
    first_repo = SqliteRepositories(db_path)
    second_repo = SqliteRepositories(db_path)
    first_repo.init_schema()
    second_repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111141"
    first_service = PublishingService(first_repo, job_id=job_id)
    second_service = PublishingService(second_repo, job_id=job_id)
    first = first_service.publish("segment-1", "youtube")
    second = second_service.publish("segment-1", "youtube")
    assert first.status == "published"
    assert second.event_type == "publish.dedup_blocked"
