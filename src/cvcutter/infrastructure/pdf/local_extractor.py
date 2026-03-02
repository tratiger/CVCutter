"""Local-first PDF text extractor adapter."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from cvcutter.domain.services.pdf_text_extractor import PdfTextExtractor
from cvcutter.domain.services.types import PdfTextBlock


class LocalPdfTextExtractor(PdfTextExtractor):
    """Extract ordered text blocks from PDF files using local libraries only."""

    def extract_text_blocks(self, pdf_path: Path) -> list[PdfTextBlock]:
        target_path = Path(pdf_path)
        if not target_path.exists():
            return []

        blocks = self._extract_with_pdfplumber(target_path)
        if blocks:
            return blocks
        return self._extract_with_pymupdf(target_path)

    @staticmethod
    def _extract_with_pdfplumber(pdf_path: Path) -> list[PdfTextBlock]:
        pdfplumber = _safe_import("pdfplumber")
        if pdfplumber is None:
            return []
        try:
            extracted: list[PdfTextBlock] = []
            with pdfplumber.open(pdf_path) as document:
                for page_index, page in enumerate(document.pages, start=1):
                    text = page.extract_text() or ""
                    for block_index, line in enumerate(text.splitlines(), start=1):
                        normalized = line.strip()
                        if not normalized:
                            continue
                        extracted.append(
                            PdfTextBlock(
                                text=normalized,
                                page_number=page_index,
                                block_index=block_index,
                            ),
                        )
            return extracted
        except Exception:
            return []

    @staticmethod
    def _extract_with_pymupdf(pdf_path: Path) -> list[PdfTextBlock]:
        fitz_module = _safe_import("fitz")
        if fitz_module is None:
            return []
        try:
            extracted: list[PdfTextBlock] = []
            with fitz_module.open(pdf_path) as document:
                for page_index, page in enumerate(document, start=1):
                    blocks = page.get_text("blocks")
                    for block_index, block in enumerate(blocks, start=1):
                        text = str(block[4]).strip() if len(block) > 4 else ""
                        if not text:
                            continue
                        extracted.append(
                            PdfTextBlock(
                                text=text,
                                page_number=page_index,
                                block_index=block_index,
                            ),
                        )
            return extracted
        except Exception:
            return []


def _safe_import(module_name: str) -> Any | None:
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None
