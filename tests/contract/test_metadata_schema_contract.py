from __future__ import annotations

from cvcutter.application.services.metadata_import_service import (
    CURRENT_SCHEMA_VERSION,
    PREVIOUS_SCHEMA_VERSION,
    normalize_metadata,
    validate_metadata_payload,
    validate_metadata_version,
)


def _canonical_record() -> dict[str, object]:
    return {
        "program_id": "P-001",
        "segment_title": "Overture",
        "performer_display_name": "Main Artist",
        "publish_visibility": "public",
        "description": "Opening piece",
        "tags": ["concert", "opening"],
        "playlist_id": "PL-01",
        "operator_note": "ok",
    }


def test_current_schema_version_payload_is_accepted() -> None:
    payload = {"schema_version": CURRENT_SCHEMA_VERSION, "records": [_canonical_record()]}
    result = validate_metadata_payload(payload, source_format="json")

    assert result.ok
    assert result.accepted_version == CURRENT_SCHEMA_VERSION
    assert result.records[0]["program_id"] == "P-001"
    assert result.warnings == []


def test_previous_schema_payload_aliases_are_mapped_to_canonical_fields() -> None:
    payload = {
        "schema_version": PREVIOUS_SCHEMA_VERSION,
        "records": [
            {
                "schema_version": PREVIOUS_SCHEMA_VERSION,
                "event_id": "P-010",
                "title": "Ballad",
                "performer": "Guest",
                "visibility": "unlisted",
            }
        ],
    }
    result = validate_metadata_payload(payload, source_format="json")

    assert result.ok
    assert result.records[0]["program_id"] == "P-010"
    assert result.records[0]["segment_title"] == "Ballad"
    assert result.records[0]["performer_display_name"] == "Guest"
    assert result.records[0]["publish_visibility"] == "unlisted"


def test_future_schema_version_is_rejected() -> None:
    payload = {"schema_version": "99", "records": [_canonical_record()]}
    result = validate_metadata_payload(payload, source_format="json")

    assert not result.ok
    assert "unsupported_schema_version" in result.errors


def test_missing_required_field_is_rejected() -> None:
    invalid = _canonical_record()
    invalid.pop("program_id")
    payload = {"schema_version": CURRENT_SCHEMA_VERSION, "records": [invalid]}
    result = validate_metadata_payload(payload, source_format="json")

    assert not result.ok
    assert "missing_required_field:program_id" in result.errors


def test_csv_mixed_schema_versions_are_rejected() -> None:
    rows = [
        {"schema_version": CURRENT_SCHEMA_VERSION, **_canonical_record()},
        {"schema_version": PREVIOUS_SCHEMA_VERSION, **_canonical_record()},
    ]
    payload = {"schema_version": CURRENT_SCHEMA_VERSION, "records": rows}
    result = validate_metadata_payload(payload, source_format="csv")

    assert not result.ok
    assert "mixed_csv_schema_versions" in result.errors


def test_unknown_fields_emit_warning_but_payload_succeeds() -> None:
    payload = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "records": [{**_canonical_record(), "custom_debug_field": "x"}],
    }
    result = validate_metadata_payload(payload, source_format="json")

    assert result.ok
    assert "unknown_field:custom_debug_field" in result.warnings
    assert "custom_debug_field" not in result.records[0]


def test_legacy_normalize_helper_maps_compat_aliases() -> None:
    normalized = normalize_metadata(
        {
            "event_id": "P-050",
            "title": "Encore",
            "performer_name": "Singer",
            "visibility": "private",
        }
    )
    assert normalized["program_id"] == "P-050"
    assert normalized["segment_title"] == "Encore"
    assert normalized["performer_display_name"] == "Singer"
    assert normalized["publish_visibility"] == "private"


def test_version_validator_accepts_only_current_or_previous() -> None:
    assert validate_metadata_version(CURRENT_SCHEMA_VERSION).ok
    assert validate_metadata_version(PREVIOUS_SCHEMA_VERSION).ok
    assert not validate_metadata_version("3").ok
