from __future__ import annotations

import pytest

from cvcutter.domain.segmentation.threshold_policy import low_confidence_threshold


def test_threshold_policy_uses_0_to_100_scale() -> None:
    assert low_confidence_threshold() == 70
    assert low_confidence_threshold(80) == 80
    assert low_confidence_threshold(0) == 0
    assert low_confidence_threshold(100) == 100


def test_threshold_policy_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError):
        low_confidence_threshold(-1)
    with pytest.raises(ValueError):
        low_confidence_threshold(101)
