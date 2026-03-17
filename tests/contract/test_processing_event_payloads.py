from cvcutter.application.dto.events import ProcessingEvent


def test_processing_event_payload_regression() -> None:
    event = ProcessingEvent("storage.warning", "j1", {"next_action": "cleanup"})
    assert event.payload["next_action"] == "cleanup"
