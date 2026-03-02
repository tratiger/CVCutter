"""Unit tests for one-time legacy artifact migration behavior.

These tests validate the foundational migration guarantees for Phase 2:
legacy file discovery, schema transformation, safe `.legacy` renaming,
idempotency, and graceful no-op handling.
"""

from __future__ import annotations

import base64

from cvcutter.application.migration_service import MigrationService
from tests.conftest import read_json, write_json


def _isolate_search_roots(monkeypatch) -> None:
    """Restrict migration discovery roots to the test-local base directory."""
    monkeypatch.setattr(MigrationService, "_legacy_search_roots", lambda self: [self.base_dir])


def test_migration_detects_legacy_files(tmp_path, monkeypatch) -> None:
    """Migration should detect and process known legacy JSON files."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)

    write_json(
        base_dir / "app_config.json",
        {
            "processing": {"video_audio_volume": 0.7},
            "workflow": {"use_gemini": True},
        },
    )
    write_json(
        base_dir / "upload_state.json",
        {
            "project_id": "legacy-project",
            "upload_history": [],
            "pending_uploads": [],
            "uploads_today": 0,
            "quota_reset_time": "2025-01-01T00:00:00+00:00",
        },
    )

    report = MigrationService(base_dir=base_dir).migrate_if_needed()

    assert any(path.endswith("config.json") for path in report.migrated_files)
    assert any(path.endswith("uploads.json") for path in report.migrated_files)
    assert any(path.endswith("quota_state.json") for path in report.migrated_files)
    assert not report.errors


def test_migration_transforms_config_to_new_schema(
    tmp_path,
    monkeypatch,
) -> None:
    """Legacy config keys should be mapped into the new ProjectConfig schema."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)

    write_json(
        base_dir / "app_config.json",
        {
            "processing": {
                "video_audio_volume": "0.25",
                "mic_audio_volume": 1.25,
                "audio_sync_sample_rate": "44100",
                "min_duration_seconds": "45",
            },
            "workflow": {
                "use_gemini": "false",
                "gemini_model": "gemini-1.5-pro",
                "youtube_chunk_size": "4096",
            },
        },
    )

    MigrationService(base_dir=base_dir).migrate_if_needed()
    migrated = read_json(base_dir / "config.json")

    assert migrated["video_audio_volume"] == 0.25
    assert migrated["mic_audio_volume"] == 1.25
    assert migrated["audio_sync_sample_rate"] == 44100
    assert migrated["min_segment_duration_seconds"] == 45.0
    assert migrated["enable_gemini"] is False
    assert migrated["gemini_model"] == "gemini-1.5-pro"
    assert migrated["youtube_chunk_size"] == 4096


def test_migration_renames_legacy_files_with_legacy_suffix(
    tmp_path,
    monkeypatch,
) -> None:
    """Migrated legacy source files should be renamed with a `.legacy` suffix."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)

    legacy_config = base_dir / "app_config.json"
    write_json(legacy_config, {"processing": {}, "workflow": {}})

    report = MigrationService(base_dir=base_dir).migrate_if_needed()
    renamed_path = base_dir / "app_config.json.legacy"

    assert not legacy_config.exists()
    assert renamed_path.exists()
    assert str(renamed_path) in report.legacy_renamed


def test_migration_is_idempotent_when_run_twice(
    tmp_path,
    monkeypatch,
) -> None:
    """A second migration run should be a no-op after marker creation."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)
    write_json(base_dir / "app_config.json", {"processing": {}, "workflow": {}})

    service = MigrationService(base_dir=base_dir)
    first_report = service.migrate_if_needed()
    second_report = service.migrate_if_needed()

    assert first_report.is_first_run is True
    assert second_report.is_first_run is False
    assert second_report.migrated_files == []
    assert second_report.legacy_renamed == []
    assert second_report.errors == []


def test_migration_handles_absent_legacy_files_gracefully(
    tmp_path,
    monkeypatch,
) -> None:
    """Migration should succeed cleanly when no legacy files exist."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)

    report = MigrationService(base_dir=base_dir).migrate_if_needed()

    assert report.is_first_run is True
    assert report.migrated_files == []
    assert report.legacy_renamed == []
    assert report.errors == []
    assert (base_dir / ".migration_complete").exists()


def test_upgrade_verification_marks_settings_preserved_when_snapshot_matches(
    tmp_path,
    monkeypatch,
) -> None:
    """Upgrade verification should succeed when config values match saved snapshot."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)
    write_json(
        base_dir / "config.json",
        {
            "video_audio_volume": 0.7,
            "output_quality": "high",
        },
    )
    write_json(
        base_dir / "upgrade_settings_snapshot.json",
        {
            "video_audio_volume": 0.7,
            "output_quality": "high",
        },
    )
    (base_dir / ".migration_complete").write_text("done", encoding="utf-8")

    report = MigrationService(base_dir=base_dir).migrate_if_needed()

    assert report.is_first_run is False
    assert report.upgrade_verified is True
    assert report.settings_preserved is True
    assert report.errors == []


def test_upgrade_verification_allows_clean_install_without_config(tmp_path, monkeypatch) -> None:
    """Upgrade verification should not report errors for clean installs without migrated config."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)
    (base_dir / ".migration_complete").write_text("done", encoding="utf-8")

    report = MigrationService(base_dir=base_dir).migrate_if_needed()

    assert report.is_first_run is False
    assert report.upgrade_verified is True
    assert report.settings_preserved is True
    assert report.errors == []


def test_upgrade_verification_bootstraps_missing_snapshot_from_current_config(
    tmp_path,
    monkeypatch,
) -> None:
    """When config exists but snapshot is missing, verification should create a baseline snapshot."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)
    write_json(
        base_dir / "config.json",
        {
            "output_quality": "high",
            "video_audio_volume": 0.6,
        },
    )
    (base_dir / ".migration_complete").write_text("done", encoding="utf-8")

    report = MigrationService(base_dir=base_dir).migrate_if_needed()
    snapshot = read_json(base_dir / "upgrade_settings_snapshot.json")

    assert report.errors == []
    assert report.settings_preserved is True
    assert snapshot["output_quality"] == "high"


def test_migration_does_not_write_marker_when_errors_occur(tmp_path, monkeypatch) -> None:
    """Migration should not mark completion when critical migration errors occur."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)
    (base_dir / "app_config.json").write_text("{invalid-json", encoding="utf-8")

    report = MigrationService(base_dir=base_dir).migrate_if_needed()

    assert report.errors
    assert not (base_dir / ".migration_complete").exists()


def test_migration_ignores_unrelated_pickle_files(tmp_path, monkeypatch) -> None:
    """Migration should ignore arbitrary .pkl files that are not known legacy credential names."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)
    (base_dir / "random.pkl").write_bytes(b"not-a-credential")

    report = MigrationService(base_dir=base_dir).migrate_if_needed()

    assert report.errors == []
    assert not (base_dir / "credentials" / "random.json").exists()
    assert (base_dir / ".migration_complete").exists()


def test_migration_converts_legacy_pickle_to_base64_payload(tmp_path, monkeypatch) -> None:
    """Known legacy pickle filenames should migrate as opaque base64 payloads without deserialization."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)
    legacy_bytes = b"raw-legacy-pickle-content"
    (base_dir / "token.pickle").write_bytes(legacy_bytes)

    report = MigrationService(base_dir=base_dir).migrate_if_needed()
    migrated = read_json(base_dir / "credentials" / "youtube_oauth.json")

    assert report.errors == []
    assert migrated["encoding"] == "base64"
    assert base64.b64decode(migrated["pickle_payload_base64"]) == legacy_bytes


def test_migration_keeps_legacy_config_when_api_key_write_fails(tmp_path, monkeypatch) -> None:
    """Legacy config should remain unrenamed when derived credential write fails."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)
    write_json(
        base_dir / "app_config.json",
        {
            "processing": {},
            "workflow": {"gemini_api_key": "test-key"},
        },
    )

    original_write_json = MigrationService._write_json

    def _fail_gemini_key(self, path, payload, report):
        if path.name == "gemini_api_key.json":
            report.errors.append("forced gemini key write failure")
            return False
        return original_write_json(self, path, payload, report)

    monkeypatch.setattr(MigrationService, "_write_json", _fail_gemini_key)
    report = MigrationService(base_dir=base_dir).migrate_if_needed()

    assert report.errors
    assert (base_dir / "app_config.json").exists()
    assert not (base_dir / "app_config.json.legacy").exists()
    assert not (base_dir / ".migration_complete").exists()


def test_migration_keeps_legacy_upload_state_when_quota_write_fails(tmp_path, monkeypatch) -> None:
    """Legacy upload state should remain for retry when quota-state persistence fails."""
    _isolate_search_roots(monkeypatch)
    base_dir = tmp_path / "appdata"
    base_dir.mkdir(parents=True)
    write_json(
        base_dir / "upload_state.json",
        {
            "project_id": "legacy-project",
            "upload_history": [],
            "pending_uploads": [],
            "uploads_today": 0,
            "quota_reset_time": "2025-01-01T00:00:00+00:00",
        },
    )

    original_write_json = MigrationService._write_json

    def _fail_quota_state(self, path, payload, report):
        if path.name == "quota_state.json":
            report.errors.append("forced quota write failure")
            return False
        return original_write_json(self, path, payload, report)

    monkeypatch.setattr(MigrationService, "_write_json", _fail_quota_state)
    report = MigrationService(base_dir=base_dir).migrate_if_needed()

    assert report.errors
    assert (base_dir / "upload_state.json").exists()
    assert not (base_dir / "upload_state.json.legacy").exists()
    assert not (base_dir / ".migration_complete").exists()
