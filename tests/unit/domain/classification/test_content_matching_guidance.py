from cvcutter.domain.classification.confidence_policy import evaluate_scores


def test_confident_threshold_rule() -> None:
    result = evaluate_scores([("A", 80), ("B", 60)])
    assert result.confidence_state == "confident"
    assert result.top_score >= 70
