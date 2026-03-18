from __future__ import annotations

from dataclasses import dataclass, field

CURRENT_SCHEMA_VERSION = "2"
PREVIOUS_SCHEMA_VERSION = "1"
SUPPORTED_SCHEMA_VERSIONS = {CURRENT_SCHEMA_VERSION, PREVIOUS_SCHEMA_VERSION}

_REQUIRED_FIELDS = (
    "program_id",
    "segment_title",
    "performer_display_name",
    "publish_visibility",
)
_OPTIONAL_FIELDS = ("description", "tags", "playlist_id", "operator_note")
_CANONICAL_FIELDS = set(_REQUIRED_FIELDS + _OPTIONAL_FIELDS)
_MAX_LENGTHS = {
    "program_id": 128,
    "segment_title": 200,
    "performer_display_name": 200,
    "description": 5000,
    "playlist_id": 128,
    "operator_note": 1000,
}
_VISIBILITY = {"public", "unlisted", "private"}
_V1_ALIAS_MAP = {
    "event_id": "program_id",
    "title": "segment_title",
    "performer": "performer_display_name",
    "visibility": "publish_visibility",
}
_LEGACY_ALIAS_MAP = {
    "performer_name": "performer_display_name",
    "song_title": "segment_title",
}


@dataclass(slots=True)
class MetadataValidationResult:
    ok: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    accepted_version: str | None = None
    records: list[dict[str, object]] = field(default_factory=list)


def normalize_metadata(row: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in row.items():
        target = _V1_ALIAS_MAP.get(key, _LEGACY_ALIAS_MAP.get(key, key))
        normalized[target] = value.strip() if isinstance(value, str) else value
    return normalized


def validate_metadata_version(version: str) -> MetadataValidationResult:
    normalized_version = version.strip()
    if normalized_version not in SUPPORTED_SCHEMA_VERSIONS:
        return MetadataValidationResult(
            ok=False,
            errors=["unsupported_schema_version"],
            warnings=[f"supported_versions:{PREVIOUS_SCHEMA_VERSION},{CURRENT_SCHEMA_VERSION}"],
        )
    return MetadataValidationResult(ok=True, accepted_version=normalized_version)


def validate_metadata_payload(payload: dict[str, object], source_format: str = "json") -> MetadataValidationResult:
    warnings: list[str] = []
    errors: list[str] = []
    schema_version = str(payload.get("schema_version", "")).strip()
    version_result = validate_metadata_version(schema_version)
    if not version_result.ok:
        return version_result

    normalized_source = source_format.strip().lower()
    if normalized_source not in {"json", "csv"}:
        return MetadataValidationResult(
            ok=False,
            errors=[f"unsupported_source_format:{source_format}"],
            accepted_version=schema_version,
        )

    raw_records = payload.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        return MetadataValidationResult(
            ok=False,
            errors=["missing_records"],
            accepted_version=schema_version,
        )

    if normalized_source == "csv":
        row_versions: set[str] = set()
        for raw_record in raw_records:
            if isinstance(raw_record, dict):
                row_version = str(raw_record.get("schema_version", "")).strip()
                if not row_version:
                    errors.append("missing_schema_version")
                else:
                    row_versions.add(row_version)
        if len(row_versions) > 1:
            errors.append("mixed_csv_schema_versions")
        if row_versions and row_versions != {schema_version}:
            errors.append("csv_schema_version_mismatch")
    else:
        for raw_record in raw_records:
            if not isinstance(raw_record, dict):
                continue
            row_version = str(raw_record.get("schema_version", "")).strip()
            if row_version and row_version != schema_version:
                errors.append("json_record_schema_version_mismatch")

    canonical_records: list[dict[str, object]] = []
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, dict):
            errors.append(f"invalid_record_type:{index}")
            continue
        normalized_record, record_warnings = _normalize_record(raw_record, schema_version)
        warnings.extend(record_warnings)
        record_errors = _validate_record(normalized_record)
        if record_errors:
            errors.extend(record_errors)
            continue
        canonical_records.append(_project_canonical_fields(normalized_record))

    if errors:
        return MetadataValidationResult(
            ok=False,
            warnings=_deduplicate(warnings),
            errors=_deduplicate(errors),
            accepted_version=schema_version,
        )
    return MetadataValidationResult(
        ok=True,
        warnings=_deduplicate(warnings),
        errors=[],
        accepted_version=schema_version,
        records=canonical_records,
    )


def _normalize_record(record: dict[str, object], schema_version: str) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    normalized = {}
    for key, value in record.items():
        if key == "schema_version":
            continue
        target_key = key
        if schema_version == PREVIOUS_SCHEMA_VERSION:
            target_key = _V1_ALIAS_MAP.get(key, key)
        if target_key not in _CANONICAL_FIELDS:
            warnings.append(f"unknown_field:{key}")
            continue
        normalized[target_key] = value.strip() if isinstance(value, str) else value
    return normalized, warnings


def _validate_record(record: dict[str, object]) -> list[str]:
    errors: list[str] = []
    for field_name in _REQUIRED_FIELDS:
        if field_name not in record or not _is_non_empty_string(record[field_name]):
            errors.append(f"missing_required_field:{field_name}")

    for field_name, max_length in _MAX_LENGTHS.items():
        value = record.get(field_name)
        if value is None:
            continue
        if not isinstance(value, str):
            errors.append(f"invalid_field_type:{field_name}")
            continue
        if len(value.strip()) > max_length:
            errors.append(f"field_too_long:{field_name}")

    visibility = record.get("publish_visibility")
    if isinstance(visibility, str):
        if visibility not in _VISIBILITY:
            errors.append("invalid_publish_visibility")
    elif visibility is not None:
        errors.append("invalid_field_type:publish_visibility")

    tags = record.get("tags")
    if tags is not None:
        parsed_tags, tag_errors = _normalize_tags(tags)
        if tag_errors:
            errors.extend(tag_errors)
        else:
            record["tags"] = parsed_tags

    return errors


def _normalize_tags(raw_tags: object) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if isinstance(raw_tags, str):
        tags = [tag.strip() for tag in raw_tags.split(";") if tag.strip()]
    elif isinstance(raw_tags, list):
        tags = []
        for raw_tag in raw_tags:
            if not isinstance(raw_tag, str):
                errors.append("invalid_tag_type")
                continue
            trimmed = raw_tag.strip()
            if trimmed:
                tags.append(trimmed)
    else:
        return [], ["invalid_field_type:tags"]

    if len(tags) > 30:
        errors.append("too_many_tags")
    for tag in tags:
        if len(tag) > 100:
            errors.append("tag_too_long")
    return tags, errors


def _project_canonical_fields(record: dict[str, object]) -> dict[str, object]:
    projected: dict[str, object] = {}
    for field_name in _REQUIRED_FIELDS + _OPTIONAL_FIELDS:
        if field_name in record:
            projected[field_name] = record[field_name]
    return projected


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
