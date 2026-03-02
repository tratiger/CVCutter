"""Contract tests for Google Sheets adapter protocol conformance (T119)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pytest

from cvcutter.infrastructure.google.sheets_client import GoogleSheetsClient

pytestmark = pytest.mark.contract


@runtime_checkable
class SheetsClientProtocol(Protocol):
    def fetch_rows(self, sheet_id: str) -> list[dict[str, str]]:
        ...

    def is_available(self) -> bool:
        ...


def test_sheets_client_satisfies_protocol() -> None:
    client = GoogleSheetsClient(rows={"sheet-1": [{"id": "s1"}]}, available=True)

    assert isinstance(client, SheetsClientProtocol)
    assert client.fetch_rows("sheet-1") == [{"id": "s1"}]
