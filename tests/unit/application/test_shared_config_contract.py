from __future__ import annotations

from typing import Any

from cvcutter.shared.config import RuntimeConfig, load_runtime_config
from cvcutter.shared.types import MetadataRecord


def test_runtime_config_defaults_are_contract_safe() -> None:
    config = load_runtime_config({})
    assert config.classification_strategy == "content_based"
    assert config.low_confidence_threshold == 70
    assert config.publish_destination == "youtube"
    assert config.title_overlay_enabled is False
    assert config.title_duration_seconds == 0


def test_runtime_config_loads_env_like_mapping() -> None:
    config = load_runtime_config(
        {
            "classification_strategy": "timestamp_based",
            "low_confidence_threshold": "82",
            "publish_destination": "youtube",
            "title_overlay_enabled": "true",
            "title_duration_seconds": "5",
        }
    )
    assert config == RuntimeConfig(
        classification_strategy="timestamp_based",
        low_confidence_threshold=82,
        publish_destination="youtube",
        title_overlay_enabled=True,
        title_duration_seconds=5,
    )


def test_runtime_config_rejects_out_of_range_threshold() -> None:
    try:
        load_runtime_config({"low_confidence_threshold": "101"})
        raise AssertionError("expected ValueError")
    except ValueError as error:
        assert "low_confidence_threshold" in str(error)


def test_runtime_config_rejects_non_binary_integer_title_overlay_flag() -> None:
    try:
        load_runtime_config({"title_overlay_enabled": 2})
        raise AssertionError("expected ValueError")
    except ValueError as error:
        assert "title_overlay_enabled" in str(error)


def test_runtime_config_rejects_non_string_non_integer_title_overlay_flag() -> None:
    try:
        invalid_values: dict[str, Any] = {"title_overlay_enabled": 0.5}
        load_runtime_config(invalid_values)
        raise AssertionError("expected ValueError")
    except ValueError as error:
        assert "title_overlay_enabled" in str(error)


def test_metadata_record_typed_dict_shape_example() -> None:
    sample: MetadataRecord = {
        "program_id": "P-001",
        "segment_title": "Opening",
        "performer_display_name": "Artist A",
        "publish_visibility": "public",
        "description": "desc",
        "tags": ["concert"],
        "playlist_id": "PL-1",
        "operator_note": "ok",
    }
    assert sample["program_id"] == "P-001"
