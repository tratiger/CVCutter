from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SetupWizardViewModel:
    source_path: str = ""
    output_path: str = ""
    metadata_path: str = ""
    classification_strategy: str = "content_based"
    recording_time_iso: str = ""
    event_window_start_iso: str = ""
    event_window_end_iso: str = ""

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.source_path:
            errors.append("missing_source_path")
        if not self.output_path:
            errors.append("missing_output_path")
        if not self.metadata_path:
            errors.append("missing_metadata_path")
        if self.classification_strategy not in {"content_based", "timestamp_based"}:
            errors.append("invalid_classification_strategy")
        if self.classification_strategy == "timestamp_based":
            if not self.recording_time_iso:
                errors.append("missing_recording_time_iso")
            if not self.event_window_start_iso:
                errors.append("missing_event_window_start_iso")
            if not self.event_window_end_iso:
                errors.append("missing_event_window_end_iso")
        return errors

    def validate(self) -> bool:
        return len(self.validation_errors()) == 0
