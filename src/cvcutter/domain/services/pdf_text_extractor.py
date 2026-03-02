"""Protocol for local-first PDF text extraction.

Adapters implementing this contract provide ordered text block extraction from
PDF documents and must degrade gracefully on unreadable files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from cvcutter.domain.services.types import PdfTextBlock


@runtime_checkable
class PdfTextExtractor(Protocol):
    """Port for mandatory local PDF extraction used as baseline parsing input."""

    def extract_text_blocks(self, pdf_path: Path) -> list[PdfTextBlock]:
        """Extract ordered text blocks from a PDF, returning [] on extraction failure."""
        ...

