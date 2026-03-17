from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MatchResult:
    strategy: str
    top_candidate: str | None
    top_score: int
    next_score: int | None
    confidence_state: str
    reason_codes: list[str]
    trace_context: dict[str, str]


def evaluate_scores(scores: list[tuple[str, int]]) -> MatchResult:
    if not scores:
        return MatchResult("name+program", None, 0, None, "no_match", ["no_candidates"], {"count": "0"})
    ranked = sorted(scores, key=lambda item: item[1], reverse=True)
    top_name, top_score = ranked[0]
    next_score = ranked[1][1] if len(ranked) > 1 else None
    margin = top_score - (next_score or 0)
    confident = top_score >= 70 and (next_score is None or margin >= 10)
    state = "confident" if confident else "review_required"
    reason = [] if confident else ["low_margin"]
    return MatchResult("name+program", top_name, top_score, next_score, state, reason, {"margin": str(margin)})
