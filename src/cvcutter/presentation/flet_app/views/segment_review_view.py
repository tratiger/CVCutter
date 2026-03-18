from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SegmentReviewView:
    tuning_mode: str = "simple"

    def decision_actions(self) -> list[str]:
        return ["accept", "adjust", "reject"]

    def switch_tuning_mode(self, mode: str) -> None:
        if mode not in {"simple", "waveform"}:
            raise ValueError("unsupported_tuning_mode")
        self.tuning_mode = mode

    def tuning_controls(self) -> list[str]:
        if self.tuning_mode == "simple":
            return ["level_slider", "noise_reduction_slider"]
        return ["waveform_preview", "waveform_offset_drag"]
