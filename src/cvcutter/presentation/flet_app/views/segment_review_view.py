from __future__ import annotations


class SegmentReviewView:
    def decision_actions(self) -> list[str]:
        return ["accept", "adjust", "reject"]
