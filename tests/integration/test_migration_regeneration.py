"""Integration checks for migration and regeneration behavior (T098)."""

from __future__ import annotations

import logging

import pytest

from cvcutter.application.migration_service import MigrationService
from tests.conftest import read_json, write_json

pytestmark = pytest.mark.integration


@pytest.fixture
def migration_base_dir(tmp_path, monkeypatch):
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(MigrationService, "_legacy_search_roots", lambda self: [self.base_dir])
    return base_dir


@pytest.fixture
def migration_service(migration_base_dir):
    return MigrationService(base_dir=migration_base_dir)


def test_migration_succeeds_on_fresh_install_without_legacy_files(migration_service, migration_base_dir) -> None:
    report = migration_service.migrate_if_needed()

    assert report.is_first_run is True
    assert report.migrated_files == []
    assert report.legacy_renamed == []
    assert report.errors == []
    assert (migration_base_dir / ".migration_complete").exists()


def test_migration_converts_legacy_config_and_upload_state(migration_service, migration_base_dir) -> None:
    write_json(
        migration_base_dir / "app_config.json",
        {
            "processing": {
                "video_audio_volume": "0.45",
                "mic_audio_volume": "1.15",
                "audio_sync_sample_rate": "44100",
                "min_duration_seconds": "42",
            },
            "workflow": {
                "use_gemini": "false",
                "gemini_model": "gemini-1.5-pro",
                "youtube_chunk_size": "8192",
            },
        },
    )
    write_json(
        migration_base_dir / "upload_state.json",
        {
            "project_id": "legacy-project",
            "upload_history": [
                {
                    "file_path": "segment_001.mp4",
                    "status": "success",
                    "upload_time": "2026-03-02T10:00:00+00:00",
                    "video_id": "video-001",
                },
            ],
            "pending_uploads": ["segment_002.mp4"],
            "uploads_today": 2,
            "quota_reset_time": "2026-03-03T00:00:00+00:00",
        },
    )

    report = migration_service.migrate_if_needed()
    config = read_json(migration_base_dir / "config.json")
    uploads = read_json(migration_base_dir / "projects" / "legacy-project" / "uploads.json")
    quota = read_json(migration_base_dir / "quota_state.json")

    assert report.errors == []
    assert config["video_audio_volume"] == 0.45
    assert config["mic_audio_volume"] == 1.15
    assert config["audio_sync_sample_rate"] == 44100
    assert config["min_segment_duration_seconds"] == 42.0
    assert config["enable_gemini"] is False
    assert config["gemini_model"] == "gemini-1.5-pro"
    assert config["youtube_chunk_size"] == 8192
    assert {row["upload_status"] for row in uploads} == {"COMPLETED", "QUEUED"}
    assert quota["daily_used"] == 2
    assert (migration_base_dir / "app_config.json.legacy").exists()
    assert (migration_base_dir / "upload_state.json.legacy").exists()


def test_migration_logs_user_visible_notice_when_legacy_data_detected(
    migration_service,
    migration_base_dir,
    caplog,
) -> None:
    write_json(
        migration_base_dir / "app_config.json",
        {
            "processing": {"video_audio_volume": 0.7},
            "workflow": {"use_gemini": True},
        },
    )

    with caplog.at_level(logging.INFO, logger="cvcutter.application.migration_service"):
        migration_service.migrate_if_needed()

    messages = "\n".join(caplog.messages)
    assert "Detected legacy config file" in messages
    assert "Legacy file renamed" in messages
