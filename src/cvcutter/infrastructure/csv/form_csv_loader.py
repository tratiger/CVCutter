"""CSV loader for performer form-response metadata."""

from __future__ import annotations

import csv
from pathlib import Path

from cvcutter.domain.models.metadata import FormResponse
from cvcutter.shared.types import PrivacySetting


class FormCsvLoader:
    """Load local CSV form responses into normalized FormResponse models."""

    def load(self, csv_path: Path) -> list[FormResponse]:
        target_path = Path(csv_path)
        if not target_path.exists():
            return []

        responses: list[FormResponse] = []
        with target_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader, start=1):
                performer_name = _field(row, "performer_name", "name")
                piece_title = _field(row, "piece_title", "title")
                if not performer_name or not piece_title:
                    continue

                response_id = _field(row, "id", "response_id") or f"csv-{index:03d}"
                responses.append(
                    FormResponse(
                        id=response_id,
                        performer_name=performer_name,
                        piece_title=piece_title,
                        privacy_preference=_privacy_from_text(_field(row, "privacy_preference", "privacy")),
                        display_name_override=_field(row, "display_name_override", "display_name"),
                        custom_description=_field(row, "custom_description", "description_extra"),
                        raw_data={str(key): str(value) for key, value in row.items() if value is not None},
                    ),
                )
        return responses


def _field(row: dict[str, str | None], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return ""


def _privacy_from_text(value: str) -> PrivacySetting:
    if not value:
        return PrivacySetting.PUBLIC
    normalized = value.strip().upper()
    try:
        return PrivacySetting(normalized)
    except ValueError:
        return PrivacySetting.PUBLIC
