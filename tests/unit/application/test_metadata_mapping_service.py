from __future__ import annotations

from cvcutter.application.services.metadata_mapping_service import map_segment_to_metadata


def test_metadata_mapping_requires_valid_publish_fields() -> None:
    ok, reason = map_segment_to_metadata(
        "segment-1",
        {
            "title": "Track",
            "description": "desc",
            "publish_visibility": "public",
        },
    )
    assert ok
    assert reason == "mapped"


def test_metadata_mapping_rejects_missing_metadata() -> None:
    ok, reason = map_segment_to_metadata("segment-1", None)
    assert not ok
    assert reason == "missing_metadata_record"
