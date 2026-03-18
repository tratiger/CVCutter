from __future__ import annotations


def map_segment_to_metadata(
    segment_id: str,
    metadata_record: dict[str, object] | str | None,
) -> tuple[bool, str]:
    if metadata_record is None:
        return False, "missing_metadata_record"
    if isinstance(metadata_record, str):
        return True, "mapped"
    required_fields = {"title", "description", "publish_visibility"}
    if not required_fields.issubset(metadata_record):
        return False, f"segment {segment_id} missing_required_publish_metadata"
    visibility = str(metadata_record["publish_visibility"])
    if visibility not in {"public", "unlisted", "private"}:
        return False, "invalid_publish_visibility"
    return True, "mapped"
