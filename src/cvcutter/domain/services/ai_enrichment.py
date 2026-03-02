"""Protocol for optional cloud AI enrichment operations.

This boundary keeps enrichment optional and failure-aware so baseline local
workflows can proceed even when cloud services are unavailable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from cvcutter.domain.models.metadata import (
        FormResponse,
        ProgramEntry,
    )
    from cvcutter.domain.models.segment import PerformanceSegment
    from cvcutter.domain.services.types import SuggestedMapping


@runtime_checkable
class AIEnrichmentService(Protocol):
    """Port for optional cloud AI enrichment with non-throwing failure behavior."""

    def parse_pdf(self, pdf_path: Path, local_entries: list[ProgramEntry]) -> list[ProgramEntry] | None:
        """Optionally enrich local PDF parsing results; return None when unavailable."""
        ...

    def match_form_responses(
        self,
        segments: list[PerformanceSegment],
        entries: list[ProgramEntry],
        responses: list[FormResponse],
    ) -> list[SuggestedMapping] | None:
        """Suggest stable-ID mappings and return None when enrichment is unavailable."""
        ...

    def is_available(self) -> bool:
        """Check whether the cloud AI enrichment backend is currently reachable."""
        ...

