"""Contract tests for mapping-related service adapters (T049)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cvcutter.domain.services.form_data_service import FormDataService
from cvcutter.domain.services.music_lookup import MusicLookupService
from cvcutter.domain.services.pdf_text_extractor import PdfTextExtractor
from cvcutter.infrastructure.forms.form_data_service import CompositeFormDataService
from cvcutter.infrastructure.google.forms_client import GoogleFormsClient
from cvcutter.infrastructure.google.sheets_client import GoogleSheetsClient
from cvcutter.infrastructure.music.sqlite_lookup import SqliteMusicLookup
from cvcutter.infrastructure.pdf.local_extractor import LocalPdfTextExtractor

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.contract


def test_local_pdf_extractor_satisfies_protocol() -> None:
    assert isinstance(LocalPdfTextExtractor(), PdfTextExtractor)


def test_sqlite_lookup_satisfies_protocol(tmp_path: Path) -> None:
    assert isinstance(SqliteMusicLookup(tmp_path / "music_lookup.db"), MusicLookupService)


def test_form_data_service_satisfies_protocol() -> None:
    assert isinstance(CompositeFormDataService(), FormDataService)


def test_form_data_service_falls_back_to_sheets_when_forms_fails() -> None:
    forms_client = GoogleFormsClient(available=True)
    sheets_client = GoogleSheetsClient(
        rows={"sheet-1": [{"id": "sheet-response", "performer_name": "Performer", "piece_title": "Piece"}]},
        available=True,
    )

    def _raise(_: str) -> list[dict[str, str]]:
        raise RuntimeError("forms unavailable")

    forms_client.fetch_responses = _raise  # type: ignore[method-assign]
    service = CompositeFormDataService(forms_client=forms_client, sheets_client=sheets_client)

    responses = service.fetch_remote(form_id="form-1", sheet_id="sheet-1")

    assert len(responses) == 1
    assert responses[0].id == "sheet-response"


def test_sqlite_lookup_rejects_unsafe_table_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        SqliteMusicLookup(tmp_path / "music_lookup.db", table_name="music;DROP TABLE x;")
