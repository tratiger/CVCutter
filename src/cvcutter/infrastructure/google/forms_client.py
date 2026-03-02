"""Google Forms adapter stub for remote response retrieval."""

from __future__ import annotations


class GoogleFormsClient:
    """Failure-tolerant Forms client stub used by form data service composition."""

    def __init__(
        self,
        *,
        responses: dict[str, list[dict[str, str]]] | None = None,
        available: bool = False,
    ) -> None:
        self._responses = {str(key): [dict(item) for item in value] for key, value in (responses or {}).items()}
        self._available = available

    def fetch_responses(self, form_id: str) -> list[dict[str, str]]:
        if not self._available:
            return []
        return [dict(item) for item in self._responses.get(form_id, [])]

    def is_available(self) -> bool:
        return self._available
