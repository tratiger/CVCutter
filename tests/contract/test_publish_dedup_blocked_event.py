from cvcutter.application.services.publishing_service import PublishingService


def test_publish_dedup_blocked_event_contract(sqlite_repo) -> None:
    service = PublishingService(sqlite_repo, job_id="job")
    service.publish("k")
    blocked = service.publish("k")
    assert blocked.event_type == "publish.dedup_blocked"
