from cvcutter.application.services.publishing_service import PublishingService


def test_publish_dedup_blocked_event_contract(sqlite_repo) -> None:
    service = PublishingService(sqlite_repo, job_id="11111111-1111-1111-1111-111111111131")
    service.publish("segment-1", "youtube")
    blocked = service.publish("segment-1", "youtube")
    assert blocked.event_type == "publish.dedup_blocked"


def test_publish_contract_surfaces_adapter_failure_message(sqlite_repo) -> None:
    service = PublishingService(sqlite_repo, job_id="11111111-1111-1111-1111-111111111132")
    failed = service.publish("segment-1", "youtube", metadata={"destination": "vimeo"})
    assert failed.status == "failed"
    assert failed.event_type == "publish.failed"
