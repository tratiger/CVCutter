from __future__ import annotations

from cvcutter.domain.classification.confidence_policy import evaluate_scores


def test_confident_threshold_rule() -> None:
    result = evaluate_scores([("A", 80), ("B", 60)])
    assert result.confidence_state == "confident"
    assert result.reason_codes == []


def test_no_confident_match_state_when_margin_is_small() -> None:
    result = evaluate_scores([("A", 75), ("B", 70)])
    assert result.confidence_state == "no_confident_match"
    assert "low_margin" in result.reason_codes
    fallback_actions = result.trace_context.get("fallback_actions")
    assert isinstance(fallback_actions, list)
    assert "switch_strategy" in fallback_actions


def test_no_confident_match_state_when_no_candidates() -> None:
    result = evaluate_scores([])
    assert result.confidence_state == "no_confident_match"
    assert "no_candidates" in result.reason_codes


def test_blocked_invalid_metadata_state_is_emitted() -> None:
    result = evaluate_scores([("A", 99)], metadata_valid=False, metadata_reason="missing_recording_time")
    assert result.confidence_state == "blocked_invalid_metadata"
    assert "missing_recording_time" in result.reason_codes
    assert result.top_candidate is None
