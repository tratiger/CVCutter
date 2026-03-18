from cvcutter.application.services.publishing_service import PublishingService


def test_publish_dedup_blocked_event_contract(sqlite_repo) -> None:
    service = PublishingService(sqlite_repo, job_id="11111111-1111-1111-1111-111111111131")
    service.publish("segment-1", "youtube")
    blocked = service.publish("segment-1", "youtube")
    assert blocked.event_type == "publish.dedup_blocked"
