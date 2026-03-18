from __future__ import annotations

from cvcutter.application.services.metadata_mapping_service import map_segment_to_metadata


def test_metadata_mapping_requires_canonical_contract_fields() -> None:
    ok, reason = map_segment_to_metadata(
        "segment-1",
        {
            "program_id": "P-001",
            "segment_title": "Track",
            "performer_display_name": "Artist",
            "publish_visibility": "public",
        },
    )
    assert ok
    assert reason == "mapped"


def test_metadata_mapping_rejects_missing_metadata() -> None:
    ok, reason = map_segment_to_metadata("segment-1", None)
    assert not ok
    assert reason == "missing_metadata_record"


def test_metadata_mapping_rejects_missing_required_canonical_fields() -> None:
    ok, reason = map_segment_to_metadata(
        "segment-1",
        {
            "segment_title": "Track",
            "performer_display_name": "Artist",
            "publish_visibility": "public",
        },
    )
    assert not ok
    assert reason.startswith("missing_required_metadata_fields:")


def test_metadata_mapping_rejects_invalid_visibility() -> None:
    ok, reason = map_segment_to_metadata(
        "segment-1",
        {
            "program_id": "P-001",
            "segment_title": "Track",
            "performer_display_name": "Artist",
            "publish_visibility": "friends_only",
        },
    )
    assert not ok
    assert reason == "invalid_publish_visibility"


def test_metadata_mapping_allows_empty_optional_description() -> None:
    ok, reason = map_segment_to_metadata(
        "segment-1",
        {
            "program_id": "P-001",
            "segment_title": "Track",
            "performer_display_name": "Artist",
            "publish_visibility": "public",
            "description": "",
        },
    )
    assert ok
    assert reason == "mapped"
