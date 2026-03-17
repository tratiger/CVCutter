from __future__ import annotations


def map_segment_to_metadata(segment_id: str, metadata_id: str | None) -> tuple[bool, str]:
    if metadata_id is None:
        return False, f"segment {segment_id} missing metadata"
    return True, "mapped"
