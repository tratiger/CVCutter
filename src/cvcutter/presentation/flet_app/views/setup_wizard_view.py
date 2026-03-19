from __future__ import annotations

from dataclasses import dataclass

from cvcutter.presentation.flet_app.viewmodel_helpers import localized
from cvcutter.presentation.flet_app.viewmodels.setup_wizard_viewmodel import SetupWizardViewModel


_ERROR_GUIDANCE = {
    "missing_source_path": "入力動画ファイルを指定してください。",
    "missing_output_path": "出力先フォルダを指定してください。",
    "missing_metadata_path": "メタデータファイルを指定してください。",
    "invalid_classification_strategy": "分類戦略が不正です。",
    "missing_recording_time_iso": "収録日時を入力してください。",
    "missing_event_window_start_iso": "イベント開始時刻を入力してください。",
    "missing_event_window_end_iso": "イベント終了時刻を入力してください。",
}


@dataclass(slots=True)
class SetupWizardView:
    viewmodel: SetupWizardViewModel

    def heading(self) -> str:
        return localized("setup.title")

    def summary(self) -> dict[str, object]:
        return {
            "title": self.heading(),
            "source_path": self.viewmodel.source_path,
            "output_path": self.viewmodel.output_path,
            "metadata_path": self.viewmodel.metadata_path,
            "classification_strategy": self.viewmodel.classification_strategy,
            "can_launch": self.viewmodel.validate(),
            "validation_guidance": self.validation_guidance(),
        }

    def validation_guidance(self) -> list[str]:
        messages: list[str] = []
        for error in self.viewmodel.validation_errors():
            messages.append(_ERROR_GUIDANCE.get(error, error))
        return messages
