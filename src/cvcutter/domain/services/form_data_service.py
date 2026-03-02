"""Protocol for loading performer form-response data.

Implementations may combine deterministic local CSV parsing with optional
remote API retrieval while preserving a single domain-facing contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from cvcutter.domain.models.metadata import FormResponse


@runtime_checkable
class FormDataService(Protocol):
    """Port for CSV/API form-response ingestion."""

    def load_csv(self, csv_path: Path) -> list[FormResponse]:
        """Load form responses from a local CSV source."""
        ...

    def fetch_remote(
        self,
        form_id: str | None = None,
        sheet_id: str | None = None,
    ) -> list[FormResponse]:
        """Fetch form responses from remote APIs, raising on missing configuration."""
        ...

