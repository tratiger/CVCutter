"""Google Sheets adapter stub for remote row retrieval."""

from __future__ import annotations


class GoogleSheetsClient:
    """Failure-tolerant Sheets client stub used by form data service composition."""

    def __init__(
        self,
        *,
        rows: dict[str, list[dict[str, str]]] | None = None,
        available: bool = False,
    ) -> None:
        self._rows = {str(key): [dict(item) for item in value] for key, value in (rows or {}).items()}
        self._available = available

    def fetch_rows(self, sheet_id: str) -> list[dict[str, str]]:
        if not self._available:
            return []
        return [dict(item) for item in self._rows.get(sheet_id, [])]

    def is_available(self) -> bool:
        return self._available
