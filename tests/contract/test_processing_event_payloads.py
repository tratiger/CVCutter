from cvcutter.application.dto.events import ProcessingEvent


def test_processing_event_payload_regression() -> None:
    event = ProcessingEvent("storage.warning", "j1", {"next_action": "cleanup"})
    assert event.payload["next_action"] == "cleanup"


def test_processing_event_contract_event_names_for_storage_threshold_family() -> None:
    warning = ProcessingEvent("storage.threshold_warning", None, {"next_action": "cleanup"})
    blocked = ProcessingEvent("storage.threshold_block", "j2", {"next_action": "free_space"})
    paused = ProcessingEvent("storage.threshold_pause", "j2", {"next_action": "pause"})

    assert warning.event_type == "storage.threshold_warning"
    assert blocked.event_type == "storage.threshold_block"
    assert paused.event_type == "storage.threshold_pause"
