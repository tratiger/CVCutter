"""Contract tests for Gemini enrichment adapter failure-aware behavior (T116)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cvcutter.infrastructure.gemini.client import GeminiEnrichmentClient

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.contract


class _FailingModel:
    def generate_content(self, prompt: str):
        del prompt
        raise RuntimeError("simulated Gemini failure")


def test_gemini_adapter_returns_none_on_failure(tmp_path: Path) -> None:
    adapter = GeminiEnrichmentClient(model=_FailingModel())
    pdf_path = tmp_path / "program.pdf"
    pdf_path.write_text("stub", encoding="utf-8")

    assert adapter.parse_pdf(pdf_path, local_entries=[]) is None
    assert adapter.match_form_responses(segments=[], entries=[], responses=[]) is None


def test_gemini_adapter_is_available_flag() -> None:
    unavailable = GeminiEnrichmentClient(model=None)
    available = GeminiEnrichmentClient(model=object())

    assert unavailable.is_available() is False
    assert available.is_available() is True
