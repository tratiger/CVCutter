from __future__ import annotations

from dataclasses import dataclass

_CONFIDENT_MIN_SCORE = 70
_CONFIDENT_MIN_MARGIN = 10


@dataclass(slots=True)
class MatchResult:
    strategy: str
    top_candidate: str | None
    top_score: int
    next_score: int | None
    confidence_state: str
    reason_codes: list[str]
    trace_context: dict[str, object]


def evaluate_scores(
    scores: list[tuple[str, int]],
    *,
    metadata_valid: bool = True,
    metadata_reason: str | None = None,
) -> MatchResult:
    if not metadata_valid:
        reason = metadata_reason or "invalid_metadata"
        return MatchResult(
            strategy="content_based",
            top_candidate=None,
            top_score=0,
            next_score=None,
            confidence_state="blocked_invalid_metadata",
            reason_codes=[reason],
            trace_context={"fallback_actions": ["switch_strategy", "fix_metadata"]},
        )

    if not scores:
        return MatchResult(
            strategy="content_based",
            top_candidate=None,
            top_score=0,
            next_score=None,
            confidence_state="no_confident_match",
            reason_codes=["no_candidates"],
            trace_context={"candidate_count": 0, "fallback_actions": ["switch_strategy", "adjust_inputs_and_retry"]},
        )

    ranked = sorted(scores, key=lambda item: item[1], reverse=True)
    top_name, top_score = ranked[0]
    next_score = ranked[1][1] if len(ranked) > 1 else None
    margin = top_score - (next_score or 0)
    confident = top_score >= _CONFIDENT_MIN_SCORE and (next_score is None or margin >= _CONFIDENT_MIN_MARGIN)
    if confident:
        return MatchResult(
            strategy="content_based",
            top_candidate=top_name,
            top_score=top_score,
            next_score=next_score,
            confidence_state="confident",
            reason_codes=[],
            trace_context={"candidate_count": len(ranked), "margin": margin},
        )

    reason_codes: list[str] = []
    if top_score < _CONFIDENT_MIN_SCORE:
        reason_codes.append("low_top_score")
    if next_score is not None and margin < _CONFIDENT_MIN_MARGIN:
        reason_codes.append("low_margin")
    if not reason_codes:
        reason_codes.append("no_confident_match")

    return MatchResult(
        strategy="content_based",
        top_candidate=top_name,
        top_score=top_score,
        next_score=next_score,
        confidence_state="no_confident_match",
        reason_codes=reason_codes,
        trace_context={
            "candidate_count": len(ranked),
            "margin": margin,
            "fallback_actions": ["switch_strategy", "adjust_inputs_and_retry"],
        },
    )
