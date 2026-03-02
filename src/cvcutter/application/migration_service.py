"""Legacy configuration/state migration service."""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from cvcutter.domain.models.project import ProjectConfig

LOGGER = logging.getLogger(__name__)


@dataclass
class MigrationReport:
    """Summary of one migration attempt."""

    migrated_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    legacy_renamed: list[str] = field(default_factory=list)
    is_first_run: bool = False
    upgrade_verified: bool = False
    settings_preserved: bool = False


class MigrationService:
    """Migrate legacy CVCutter artifacts into the new local-appdata schema."""

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize migration service paths."""
        self.base_dir = base_dir if base_dir is not None else self._default_base_dir()
        self.marker_path = self.base_dir / ".migration_complete"
        self.upgrade_snapshot_path = self.base_dir / "upgrade_settings_snapshot.json"

    def migrate_if_needed(self) -> MigrationReport:
        """Run one-time migration when no completion marker exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        report = MigrationReport(is_first_run=not self.marker_path.exists())

        if self.marker_path.exists():
            LOGGER.info("Migration already completed; marker present at %s", self.marker_path)
            self._verify_upgrade_settings(report)
            return report

        LOGGER.info("Starting legacy migration in %s", self.base_dir)

        for config_file in self._find_legacy_named_files("app_config.json"):
            self._migrate_legacy_config(config_file, report)

        for upload_state_file in self._find_legacy_named_files("upload_state.json"):
            self._migrate_legacy_upload_state(upload_state_file, report)

        for pickle_file in self._find_legacy_pickle_files():
            self._migrate_legacy_pickle(pickle_file, report)

        if not report.migrated_files and not report.errors:
            LOGGER.info("No legacy files were found; migration completed as no-op.")

        if report.errors:
            LOGGER.warning("Migration encountered errors; completion marker was not written.")
            return report

        self._persist_upgrade_settings_snapshot(report)
        if report.errors:
            LOGGER.warning("Migration snapshot persistence failed; completion marker was not written.")
            return report

        try:
            self.marker_path.write_text(datetime.now(UTC).isoformat(), encoding="utf-8")
            LOGGER.info("Migration marker created at %s", self.marker_path)
        except OSError as exc:
            message = f"Failed to write migration marker: {exc}"
            LOGGER.error(message)
            report.errors.append(message)

        return report

    def _persist_upgrade_settings_snapshot(self, report: MigrationReport) -> None:
        """Persist a baseline snapshot of settings used for upgrade verification."""
        config_payload = self._read_json_optional(self.base_dir / "config.json")
        if config_payload is None:
            return
        self._write_json(self.upgrade_snapshot_path, config_payload, report)

    def _verify_upgrade_settings(self, report: MigrationReport) -> None:
        """Verify that configured settings remain stable across upgraded runs."""
        report.upgrade_verified = True
        current_config = self._read_json_optional(self.base_dir / "config.json")
        snapshot = self._read_json_optional(self.upgrade_snapshot_path)
        if current_config is None and snapshot is None:
            report.settings_preserved = True
            return
        if current_config is None:
            report.errors.append("Upgrade verification failed: config.json is missing.")
            return
        if snapshot is None:
            if self._write_json(self.upgrade_snapshot_path, current_config, report):
                report.settings_preserved = True
            return

        drifted_keys = [
            key
            for key, previous_value in snapshot.items()
            if key not in current_config or current_config[key] != previous_value
        ]
        if drifted_keys:
            report.errors.append(
                "Upgrade verification failed: settings changed unexpectedly "
                f"for keys {', '.join(sorted(drifted_keys))}.",
            )
            return
        report.settings_preserved = True

    @staticmethod
    def _read_json_optional(path: Path) -> dict[str, Any] | None:
        """Read a JSON object from disk, returning None for missing/invalid files."""
        if not path.exists():
            return None
        try:
            with path.open(encoding="utf-8") as file_handle:
                loaded = json.load(file_handle)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(loaded, dict):
            return None
        return loaded

    @staticmethod
    def _default_base_dir() -> Path:
        """Resolve default app data directory path."""
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "cvcutter"
        return Path.home() / "AppData" / "Local" / "cvcutter"

    def _legacy_search_roots(self) -> list[Path]:
        """Return directories where legacy files are expected."""
        roots: set[Path] = {self.base_dir, Path.cwd(), self._project_root(), self._package_root()}
        existing = [path for path in roots if path.exists() and path.is_dir()]
        return sorted(existing, key=lambda value: str(value).lower())

    def _find_legacy_named_files(self, filename: str) -> list[Path]:
        """Detect legacy files by exact name in known roots."""
        found: set[Path] = set()
        for root in self._legacy_search_roots():
            candidate = root / filename
            if candidate.exists() and candidate.is_file():
                found.add(candidate.resolve())
        return sorted(found, key=lambda value: str(value).lower())

    def _find_legacy_pickle_files(self) -> list[Path]:
        """Detect legacy pickle files in known roots."""
        found: set[Path] = set()
        legacy_names = ("token.pickle", "token.pkl", "forms_token.pickle", "forms_token.pkl")
        for root in self._legacy_search_roots():
            for legacy_name in legacy_names:
                candidate = root / legacy_name
                if candidate.is_file() and not candidate.name.endswith(".legacy"):
                    found.add(candidate.resolve())
        return sorted(found, key=lambda value: str(value).lower())

    def _migrate_legacy_config(self, source_path: Path, report: MigrationReport) -> None:
        """Transform legacy app_config.json to config.json."""
        LOGGER.info("Detected legacy config file: %s", source_path)
        payload = self._read_json(source_path, report)
        if payload is None:
            return

        new_config = self._transform_config_payload(payload)
        config_path = self.base_dir / "config.json"
        config_written = self._write_json(config_path, new_config, report)
        api_key_written = True

        gemini_api_key = self._extract_gemini_api_key(payload)
        if gemini_api_key:
            api_key_written = self._write_json(
                self.base_dir / "credentials" / "gemini_api_key.json",
                {"api_key": gemini_api_key},
                report,
            )

        if config_written and api_key_written:
            self._rename_legacy_file(source_path, report)

    def _migrate_legacy_upload_state(self, source_path: Path, report: MigrationReport) -> None:
        """Transform legacy upload_state.json to project uploads.json + quota_state.json."""
        LOGGER.info("Detected legacy upload state file: %s", source_path)
        payload = self._read_json(source_path, report)
        if payload is None:
            return

        project_id = self._sanitize_project_id(payload.get("project_id"))
        project_dir = self.base_dir / "projects" / project_id
        uploads_path = project_dir / "uploads.json"
        quota_path = self.base_dir / "quota_state.json"

        uploads_written = self._write_json(uploads_path, self._transform_upload_state(payload), report)
        quota_written = self._write_json(quota_path, self._transform_quota_state(payload), report)
        if uploads_written and quota_written:
            self._rename_legacy_file(source_path, report)

    def _migrate_legacy_pickle(self, source_path: Path, report: MigrationReport) -> None:
        """Convert legacy pickle credential files to JSON records without deserializing pickle data."""
        LOGGER.info("Detected legacy pickle file: %s", source_path)
        credentials_dir = self.base_dir / "credentials"
        target_path = credentials_dir / self._credential_json_name(source_path.name)

        try:
            raw_payload = source_path.read_bytes()
        except OSError as exc:
            message = f"Failed to read pickle bytes {source_path}: {exc}"
            LOGGER.error(message)
            report.errors.append(message)
            return

        payload = {
            "service": target_path.stem,
            "source_file": str(source_path),
            "migrated_at_utc": datetime.now(UTC).isoformat(),
            "encoding": "base64",
            "pickle_payload_base64": base64.b64encode(raw_payload).decode("ascii"),
        }
        if self._write_json(target_path, payload, report):
            self._rename_legacy_file(source_path, report)

    def _transform_config_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Map legacy config structure into ProjectConfig-compatible JSON."""
        defaults = ProjectConfig()
        processing_raw = payload.get("processing")
        workflow_raw = payload.get("workflow")
        processing: dict[str, Any] = processing_raw if isinstance(processing_raw, dict) else {}
        workflow: dict[str, Any] = workflow_raw if isinstance(workflow_raw, dict) else {}

        candidate = asdict(defaults)
        candidate["video_audio_volume"] = self._coerce_float(
            processing.get("video_audio_volume"),
            defaults.video_audio_volume,
        )
        candidate["mic_audio_volume"] = self._coerce_float(
            processing.get("mic_audio_volume"),
            defaults.mic_audio_volume,
        )
        candidate["audio_sync_sample_rate"] = self._coerce_int(
            processing.get("audio_sync_sample_rate"),
            defaults.audio_sync_sample_rate,
        )
        candidate["min_segment_duration_seconds"] = self._coerce_float(
            processing.get("min_duration_seconds"),
            defaults.min_segment_duration_seconds,
        )
        candidate["enable_gemini"] = self._coerce_bool(
            workflow.get("use_gemini"),
            defaults.enable_gemini,
        )
        candidate["gemini_model"] = self._coerce_str(workflow.get("gemini_model"), defaults.gemini_model)
        candidate["youtube_chunk_size"] = self._coerce_int(
            workflow.get("youtube_chunk_size"),
            defaults.youtube_chunk_size,
        )

        try:
            validated = ProjectConfig(**candidate)
        except (TypeError, ValueError):
            LOGGER.warning("Migrated config invalid; writing ProjectConfig defaults instead.")
            validated = defaults

        return asdict(validated)

    def _transform_upload_state(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert legacy upload history/pending queue into UploadRecord-like rows."""
        records: list[dict[str, Any]] = []
        history_raw = payload.get("upload_history")
        pending_raw = payload.get("pending_uploads")
        history: list[Any] = history_raw if isinstance(history_raw, list) else []
        pending: list[Any] = pending_raw if isinstance(pending_raw, list) else []

        for index, item in enumerate(history):
            if not isinstance(item, dict):
                continue
            file_path = self._coerce_str(item.get("file_path"), f"legacy-history-{index}")
            status = self._map_legacy_upload_status(item.get("status"))
            upload_time = self._coerce_str(item.get("upload_time"), "")
            video_id = self._coerce_str(item.get("video_id"), "") or None
            error_detail = self._coerce_str(item.get("error"), "") or None

            records.append(
                self._build_upload_record(
                    file_path=file_path,
                    status=status,
                    upload_time=upload_time or None,
                    video_id=video_id,
                    error_detail=error_detail,
                ),
            )

        for index, pending_item in enumerate(pending):
            file_path = self._coerce_str(pending_item, f"legacy-pending-{index}")
            records.append(
                self._build_upload_record(
                    file_path=file_path,
                    status="QUEUED",
                    upload_time=None,
                    video_id=None,
                    error_detail=None,
                ),
            )

        return records

    def _transform_quota_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Convert quota fields from upload_state.json to quota_state.json schema."""
        daily_limit = 10_000
        daily_used = self._coerce_int(payload.get("uploads_today"), 0)
        daily_used = min(max(daily_used, 0), daily_limit)
        reset_at = self._coerce_str(payload.get("quota_reset_time"), datetime.now(UTC).isoformat())
        now = datetime.now(UTC).isoformat()
        return {
            "daily_limit": daily_limit,
            "daily_used": daily_used,
            "reset_timestamp_utc": reset_at,
            "last_updated": now,
        }

    def _build_upload_record(
        self,
        *,
        file_path: str,
        status: str,
        upload_time: str | None,
        video_id: str | None,
        error_detail: str | None,
    ) -> dict[str, Any]:
        """Build one migrated upload record dictionary."""
        segment_id = str(uuid5(NAMESPACE_URL, f"legacy-segment:{file_path}"))
        mapping_id = str(uuid5(NAMESPACE_URL, f"legacy-mapping:{file_path}"))
        record_id = str(uuid5(NAMESPACE_URL, f"legacy-record:{file_path}:{upload_time or ''}:{video_id or ''}"))
        return {
            "id": record_id,
            "segment_id": segment_id,
            "mapping_id": mapping_id,
            "youtube_video_id": video_id,
            "upload_status": status,
            "privacy_setting": "PUBLIC",
            "playlist_id": None,
            "quota_cost": 1600,
            "retry_count": 0,
            "error_detail": error_detail,
            "resumable_upload_uri": None,
            "bytes_uploaded": 0,
            "failure_kind": "UNKNOWN" if status == "FAILED" else None,
            "session_invalidated_at_utc": None,
            "restart_from_zero": False,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
            "uploaded_at": upload_time if status == "COMPLETED" else None,
        }

    def _map_legacy_upload_status(self, status: Any) -> str:
        """Map legacy upload status text to new enum-like values."""
        normalized = self._coerce_str(status, "pending").strip().lower()
        if normalized in {"success", "completed", "done", "uploaded"}:
            return "COMPLETED"
        if normalized in {"failed", "error"}:
            return "FAILED"
        if normalized in {"queued", "waiting", "pending"}:
            return "QUEUED"
        return "PENDING"

    def _extract_gemini_api_key(self, payload: dict[str, Any]) -> str | None:
        """Extract legacy Gemini API key from workflow settings when present."""
        workflow = payload.get("workflow")
        if not isinstance(workflow, dict):
            return None
        api_key = workflow.get("gemini_api_key")
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()
        return None

    def _read_json(self, path: Path, report: MigrationReport) -> dict[str, Any] | None:
        """Read a JSON file into a dictionary, collecting errors in report."""
        try:
            with path.open(encoding="utf-8") as file_handle:
                loaded = json.load(file_handle)
        except (OSError, json.JSONDecodeError) as exc:
            message = f"Failed to read JSON {path}: {exc}"
            LOGGER.error(message)
            report.errors.append(message)
            return None
        if not isinstance(loaded, dict):
            message = f"Expected JSON object in {path}, got {type(loaded).__name__}"
            LOGGER.error(message)
            report.errors.append(message)
            return None
        return loaded

    def _write_json(self, path: Path, payload: Any, report: MigrationReport) -> bool:
        """Write JSON payload and record migrated file path."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as file_handle:
                json.dump(payload, file_handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            message = f"Failed to write JSON {path}: {exc}"
            LOGGER.error(message)
            report.errors.append(message)
            return False
        report.migrated_files.append(str(path))
        LOGGER.info("Migrated file written: %s", path)
        return True

    def _rename_legacy_file(self, source_path: Path, report: MigrationReport) -> None:
        """Rename legacy source files with .legacy suffix."""
        target = source_path.with_name(f"{source_path.name}.legacy")
        if target.exists():
            timestamp = int(datetime.now(UTC).timestamp())
            target = source_path.with_name(f"{source_path.stem}_{timestamp}{source_path.suffix}.legacy")

        try:
            source_path.rename(target)
        except OSError as exc:
            message = f"Failed to rename legacy file {source_path}: {exc}"
            LOGGER.error(message)
            report.errors.append(message)
            return

        report.legacy_renamed.append(str(target))
        LOGGER.info("Legacy file renamed: %s -> %s", source_path, target)

    def _sanitize_project_id(self, value: Any) -> str:
        """Normalize migrated project id text."""
        text = self._coerce_str(value, "legacy-default")
        safe = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in text.strip())
        return safe or "legacy-default"

    def _credential_json_name(self, pickle_name: str) -> str:
        """Map known pickle filenames to credential JSON filenames."""
        lowered = pickle_name.lower()
        mapping = {
            "token.pickle": "youtube_oauth.json",
            "token.pkl": "youtube_oauth.json",
            "forms_token.pickle": "forms_oauth.json",
            "forms_token.pkl": "forms_oauth.json",
        }
        return mapping.get(lowered, f"{Path(pickle_name).stem}.json")

    def _to_jsonable_credential_payload(self, value: Any) -> Any:
        """Convert arbitrary loaded pickle payload into JSON-serializable data."""
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, dict):
            return {str(key): self._to_jsonable_credential_payload(data) for key, data in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._to_jsonable_credential_payload(item) for item in value]
        if hasattr(value, "to_json") and callable(value.to_json):
            try:
                serialized = value.to_json()
                if isinstance(serialized, (str, bytes, bytearray)):
                    return json.loads(serialized)
                return self._to_jsonable_credential_payload(serialized)
            except Exception:
                return str(value)
        if hasattr(value, "__dict__"):
            return {
                key: self._to_jsonable_credential_payload(data)
                for key, data in vars(value).items()
                if not key.startswith("_")
            }
        return str(value)

    @staticmethod
    def _coerce_bool(value: Any, fallback: bool) -> bool:
        """Coerce value to bool with fallback."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
            return fallback
        if isinstance(value, (int, float)):
            return bool(value)
        return fallback

    @staticmethod
    def _coerce_int(value: Any, fallback: int) -> int:
        """Coerce value to int with fallback."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_float(value: Any, fallback: float) -> float:
        """Coerce value to float with fallback."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_str(value: Any, fallback: str) -> str:
        """Coerce value to string with fallback."""
        if value is None:
            return fallback
        return str(value)

    @staticmethod
    def _package_root() -> Path:
        """Return current package root (.../src/cvcutter)."""
        return Path(__file__).resolve().parents[1]

    @staticmethod
    def _project_root() -> Path:
        """Return project root when running from source tree."""
        resolved = Path(__file__).resolve()
        if len(resolved.parents) > 3:
            return resolved.parents[3]
        return Path.cwd()
