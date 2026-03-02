"""Composite form-data service combining local CSV and optional remote sources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cvcutter.domain.models.metadata import FormResponse
from cvcutter.domain.services.form_data_service import FormDataService
from cvcutter.infrastructure.csv.form_csv_loader import FormCsvLoader
from cvcutter.shared.types import PrivacySetting

if TYPE_CHECKING:
    from pathlib import Path

    from cvcutter.infrastructure.google.forms_client import GoogleFormsClient
    from cvcutter.infrastructure.google.sheets_client import GoogleSheetsClient


class CompositeFormDataService(FormDataService):
    """Load form data from CSV and optional remote Forms/Sheets adapters."""

    def __init__(
        self,
        *,
        csv_loader: FormCsvLoader | None = None,
        forms_client: GoogleFormsClient | None = None,
        sheets_client: GoogleSheetsClient | None = None,
    ) -> None:
        self._csv_loader = csv_loader or FormCsvLoader()
        self._forms_client = forms_client
        self._sheets_client = sheets_client

    def load_csv(self, csv_path: Path) -> list[FormResponse]:
        return self._csv_loader.load(csv_path)

    def fetch_remote(
        self,
        form_id: str | None = None,
        sheet_id: str | None = None,
    ) -> list[FormResponse]:
        if form_id and self._forms_client is not None and self._forms_client.is_available():
            try:
                rows = self._forms_client.fetch_responses(form_id)
            except Exception:
                rows = []
            if rows:
                return _rows_to_responses(rows, prefix="form")
        if sheet_id and self._sheets_client is not None and self._sheets_client.is_available():
            try:
                rows = self._sheets_client.fetch_rows(sheet_id)
            except Exception:
                rows = []
            if rows:
                return _rows_to_responses(rows, prefix="sheet")
        return []


def _rows_to_responses(rows: list[dict[str, str]], *, prefix: str) -> list[FormResponse]:
    responses: list[FormResponse] = []
    for index, row in enumerate(rows, start=1):
        performer_name = _field(row, "performer_name", "name")
        piece_title = _field(row, "piece_title", "title")
        if not performer_name or not piece_title:
            continue
        response_id = _field(row, "id", "response_id") or f"{prefix}-{index:03d}"
        responses.append(
            FormResponse(
                id=response_id,
                performer_name=performer_name,
                piece_title=piece_title,
                privacy_preference=_privacy(_field(row, "privacy_preference", "privacy")),
                display_name_override=_field(row, "display_name_override", "display_name") or None,
                custom_description=_field(row, "custom_description", "description_extra") or None,
                raw_data={str(key): str(value) for key, value in row.items()},
            ),
        )
    return responses


def _field(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key not in row:
            continue
        text = str(row[key]).strip()
        if text:
            return text
    return ""


def _privacy(value: str) -> PrivacySetting:
    if not value:
        return PrivacySetting.PUBLIC
    try:
        return PrivacySetting(value.upper())
    except ValueError:
        return PrivacySetting.PUBLIC
