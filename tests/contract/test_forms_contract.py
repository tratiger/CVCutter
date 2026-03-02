"""Contract tests for Google Forms adapter protocol conformance (T119)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pytest

from cvcutter.infrastructure.google.forms_client import GoogleFormsClient

pytestmark = pytest.mark.contract


@runtime_checkable
class FormsClientProtocol(Protocol):
    def fetch_responses(self, form_id: str) -> list[dict[str, str]]:
        ...

    def is_available(self) -> bool:
        ...


def test_forms_client_satisfies_protocol() -> None:
    client = GoogleFormsClient(responses={"form-1": [{"id": "r1"}]}, available=True)

    assert isinstance(client, FormsClientProtocol)
    assert client.fetch_responses("form-1") == [{"id": "r1"}]
