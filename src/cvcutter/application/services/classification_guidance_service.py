from __future__ import annotations

from cvcutter.domain.classification.confidence_policy import MatchResult, evaluate_scores


class ClassificationGuidanceService:
    def guide(self, scores: list[tuple[str, int]]) -> MatchResult:
        return evaluate_scores(scores)
