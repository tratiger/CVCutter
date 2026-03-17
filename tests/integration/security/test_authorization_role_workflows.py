import pytest

from cvcutter.domain.policies.authorization_policy import enforce_executable_role


def test_authorization_role_workflow() -> None:
    enforce_executable_role("operator")
    with pytest.raises(PermissionError):
        enforce_executable_role("publisher")
