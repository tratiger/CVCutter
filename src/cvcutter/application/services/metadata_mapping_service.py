from __future__ import annotations

from collections.abc import Iterable

_REQUIRED_FIELDS = {
    "program_id",
    "segment_title",
    "performer_display_name",
    "publish_visibility",
}
_ALLOWED_VISIBILITY = {"public", "unlisted", "private"}


def _is_non_empty_string(value: object, max_len: int) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    return 0 < len(normalized) <= max_len


def _is_string_with_max_len(value: object, max_len: int) -> bool:
    if not isinstance(value, str):
        return False
    return len(value) <= max_len


def _validate_tags(tags: object) -> bool:
    if not isinstance(tags, Iterable) or isinstance(tags, (str, bytes)):
        return False
    values = list(tags)
    if len(values) > 30:
        return False
    return all(isinstance(tag, str) and 0 < len(tag.strip()) <= 100 for tag in values)


def map_segment_to_metadata(segment_id: str, metadata_record: dict[str, object] | None) -> tuple[bool, str]:
    if metadata_record is None:
        return False, "missing_metadata_record"
    if not isinstance(metadata_record, dict):
        return False, "invalid_metadata_record_type"

    missing = sorted(_REQUIRED_FIELDS - set(metadata_record))
    if missing:
        return False, f"missing_required_metadata_fields:{','.join(missing)}"

    if not _is_non_empty_string(metadata_record["program_id"], 128):
        return False, f"segment {segment_id} invalid_program_id"
    if not _is_non_empty_string(metadata_record["segment_title"], 200):
        return False, f"segment {segment_id} invalid_segment_title"
    if not _is_non_empty_string(metadata_record["performer_display_name"], 200):
        return False, f"segment {segment_id} invalid_performer_display_name"

    visibility = str(metadata_record["publish_visibility"]).strip().lower()
    if visibility not in _ALLOWED_VISIBILITY:
        return False, "invalid_publish_visibility"

    if "description" in metadata_record and not _is_string_with_max_len(metadata_record["description"], 5000):
        return False, f"segment {segment_id} invalid_description"
    if "tags" in metadata_record and not _validate_tags(metadata_record["tags"]):
        return False, f"segment {segment_id} invalid_tags"

    return True, "mapped"
