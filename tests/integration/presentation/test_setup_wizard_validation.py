from cvcutter.presentation.flet_app.viewmodels.setup_wizard_viewmodel import SetupWizardViewModel
from cvcutter.presentation.flet_app.views.setup_wizard_view import SetupWizardView


def test_setup_wizard_validation() -> None:
    vm = SetupWizardViewModel(
        source_path="in.mp4",
        output_path="out",
        metadata_path="meta.json",
        classification_strategy="timestamp_based",
        recording_time_iso="2026-03-14T18:05:00+09:00",
        event_window_start_iso="2026-03-14T18:00:00+09:00",
        event_window_end_iso="2026-03-14T21:00:00+09:00",
    )
    assert vm.validate()
    assert vm.validation_errors() == []


def test_setup_wizard_blocks_missing_strategy_specific_fields() -> None:
    vm = SetupWizardViewModel(
        source_path="in.mp4",
        output_path="out",
        metadata_path="meta.json",
        classification_strategy="timestamp_based",
    )
    assert not vm.validate()
    assert "missing_recording_time_iso" in vm.validation_errors()


def test_setup_wizard_view_exposes_validation_guidance() -> None:
    vm = SetupWizardViewModel(classification_strategy="timestamp_based")
    summary = SetupWizardView(vm).summary()
    assert summary["title"] == "セットアップ"
    assert summary["can_launch"] is False
    guidance = summary["validation_guidance"]
    assert isinstance(guidance, list)
    assert any("収録日時" in message for message in guidance)
