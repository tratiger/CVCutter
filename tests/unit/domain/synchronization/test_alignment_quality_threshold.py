from cvcutter.domain.synchronization.alignment_quality_policy import is_alignment_within_tolerance


def test_alignment_tolerance_80ms() -> None:
    assert is_alignment_within_tolerance(80)
    assert not is_alignment_within_tolerance(90)
