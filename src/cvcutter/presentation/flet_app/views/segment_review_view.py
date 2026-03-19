from __future__ import annotations

from dataclasses import dataclass


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

    def summary(self) -> dict[str, object]:
        return {
            "tuning_mode": self.tuning_mode,
            "review_status": self.review_status,
            "selected_action": self.selected_action,
            "controls": self.tuning_controls(),
        }
