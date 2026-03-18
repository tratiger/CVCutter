from cvcutter.domain.synchronization.alignment_quality_policy import (
    evaluate_alignment_quality,
    is_alignment_within_tolerance,
)


def test_alignment_tolerance_80ms() -> None:
    assert is_alignment_within_tolerance(80)
    assert not is_alignment_within_tolerance(90)


def test_alignment_uses_median_of_offsets() -> None:
    result = evaluate_alignment_quality([10, 20, 30, 200])
    assert result["median_error_ms"] == 25
    assert result["status"] == "ok"
