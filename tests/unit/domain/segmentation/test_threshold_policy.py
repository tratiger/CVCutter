from __future__ import annotations

from cvcutter.domain.segmentation.threshold_policy import low_confidence_threshold


def test_threshold_policy_uses_0_to_100_scale() -> None:
    assert low_confidence_threshold("default") == 70
    assert low_confidence_threshold("strict") == 80
