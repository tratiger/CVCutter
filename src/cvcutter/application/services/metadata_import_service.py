from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MetadataValidationResult:
    ok: bool
    warnings: list[str]


def normalize_metadata(row: dict[str, str]) -> dict[str, str]:
    aliases = {"performer_name": "performer", "song_title": "title"}
    normalized = {}
    for key, value in row.items():
        normalized[aliases.get(key, key)] = value
    return normalized


def validate_metadata_version(version: str) -> MetadataValidationResult:
    if version != "v1":
        return MetadataValidationResult(False, ["unsupported_version"])
    return MetadataValidationResult(True, [])
