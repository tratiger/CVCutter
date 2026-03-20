from pathlib import Path

from cvcutter.application.services.publishing_service import PublishingService
from cvcutter.infrastructure.integrations.adapters import AdapterResult
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


def test_publish_reports_provider_blocking_and_allows_retry_after_fix(tmp_path: Path) -> None:
    db_path = tmp_path / "publish-retry.db"
    repo = SqliteRepositories(db_path)
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111142"
    service = PublishingService(repo, job_id=job_id)

    first = service.publish("segment-1", "youtube", metadata={"destination": "vimeo"})
    assert first.status == "failed"
    assert first.event_type == "publish.failed"

    retried = service.publish("segment-1", "youtube")
    assert retried.status == "published"
    assert retried.event_type == "publish.completed"


class _RaisingPublishAdapter:
    def publish_segment(self, segment_id: str, metadata: dict[str, object], *, job_id: str) -> AdapterResult:
        raise RuntimeError("adapter exploded")


def test_publish_rolls_back_dedup_key_when_adapter_raises(tmp_path: Path) -> None:
    db_path = tmp_path / "publish-exception-retry.db"
    repo = SqliteRepositories(db_path)
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111143"
    service = PublishingService(repo, job_id=job_id, adapters=_RaisingPublishAdapter())

    first = service.publish("segment-1", "youtube")
    second = service.publish("segment-1", "youtube")

    assert first.status == "failed"
    assert first.event_type == "publish.failed"
    assert second.status == "failed"
    assert second.event_type == "publish.failed"
