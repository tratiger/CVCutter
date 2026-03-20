from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from cvcutter.presentation.flet_app.viewmodel_helpers import localized


@dataclass(slots=True)
class SegmentReviewView:
    tuning_mode: str = "simple"
    review_status: str = "pending"
    selected_action: str | None = None

    def decision_actions(self) -> list[str]:
        return ["accept", "adjust", "reject"]

    def apply_decision(self, action: str) -> None:
        if action not in self.decision_actions():
            raise ValueError("unsupported_review_action")
        self.selected_action = action
        mapping = {"accept": "accepted", "adjust": "adjusted", "reject": "rejected"}
        self.review_status = mapping[action]

    def switch_tuning_mode(self, mode: str) -> None:
        if mode not in {"simple", "waveform"}:
            raise ValueError("unsupported_tuning_mode")
        self.tuning_mode = mode

    def tuning_controls(self) -> list[str]:
        if self.tuning_mode == "simple":
            return ["level_slider", "noise_reduction_slider"]
        return ["waveform_preview", "waveform_offset_drag"]

    def build_controls(self) -> list[ft.Control]:
        action_buttons: list[ft.Control] = []
        for action in self.decision_actions():
            action_buttons.append(
                ft.OutlinedButton(
                    content=ft.Text(action.capitalize()),
                    disabled=self.selected_action == action,
                )
            )
        return [
            ft.Text(localized("review.title"), size=20),
            ft.Text(f"Tuning mode: {self.tuning_mode}"),
            ft.Row(action_buttons),
            ft.Text(f"Review status: {self.review_status}"),
            ft.Text(f"Available controls: {', '.join(self.tuning_controls())}"),
        ]

    def summary(self) -> dict[str, object]:
        return {
            "tuning_mode": self.tuning_mode,
            "review_status": self.review_status,
            "selected_action": self.selected_action,
            "controls": self.tuning_controls(),
        }
