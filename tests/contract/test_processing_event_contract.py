from cvcutter.application.dto.events import ProcessingEvent


def test_processing_event_contract() -> None:
    event = ProcessingEvent("job.created", None, {"retry": {"attempt": 1}})
    assert event.event_type == "job.created"
    assert "retry" in event.payload
