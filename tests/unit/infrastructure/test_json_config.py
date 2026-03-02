"""Unit tests for JSON-backed global configuration persistence.

These tests define baseline behavior for configuration persistence:
round-trip integrity, default fallback when file is absent, and partial
payload merge semantics against ProjectConfig defaults.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from cvcutter.domain.models.project import ProjectConfig
from cvcutter.infrastructure.persistence.json_config import JsonConfig


def test_config_round_trip_save_then_load_produces_same_values(tmp_path) -> None:
    """Saving then loading config should preserve all configured values."""
    store = JsonConfig(base_dir=tmp_path)
    expected = ProjectConfig(
        video_audio_volume=0.4,
        mic_audio_volume=1.2,
        audio_sync_sample_rate=44_100,
        enable_gemini=False,
        gemini_model="gemini-1.5-pro",
        youtube_chunk_size=4_096,
    )

    store.save_config(expected)
    loaded = store.load_config()

    assert asdict(loaded) == asdict(expected)


def test_missing_config_file_returns_defaults(tmp_path) -> None:
    """Loading with no config.json present should return ProjectConfig defaults."""
    store = JsonConfig(base_dir=tmp_path)

    loaded = store.load_config()

    assert asdict(loaded) == asdict(ProjectConfig())


def test_partial_config_merge_with_defaults(tmp_path) -> None:
    """Partial raw config should merge with default values for omitted fields."""
    partial_payload = {
        "video_audio_volume": 0.9,
        "gemini_model": "gemini-2.5-pro",
    }
    (tmp_path / "config.json").write_text(json.dumps(partial_payload), encoding="utf-8")

    store = JsonConfig(base_dir=tmp_path)
    loaded = asdict(store.load_config())
    defaults = asdict(ProjectConfig())

    assert loaded["video_audio_volume"] == 0.9
    assert loaded["gemini_model"] == "gemini-2.5-pro"
    for key, default_value in defaults.items():
        if key not in partial_payload:
            assert loaded[key] == default_value
