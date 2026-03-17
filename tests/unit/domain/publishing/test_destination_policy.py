import pytest

from cvcutter.domain.policies.destination_policy import ensure_destination_allowed


def test_non_approved_destination_blocked() -> None:
    with pytest.raises(ValueError):
        ensure_destination_allowed("youtube", "vimeo")
