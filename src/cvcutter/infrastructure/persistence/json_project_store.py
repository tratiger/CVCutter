"""JSON-backed adapter for project aggregate persistence."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from cvcutter.domain.models.metadata import (
    FormResponse,
    MatchSignal,
    ProgramEntry,
    VideoMetadataMapping,
)
from cvcutter.domain.models.project import ConcertProject, ExternalAudio, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import DetectionSignal, PerformanceSegment
from cvcutter.domain.models.upload import UploadRecord
from cvcutter.domain.services.project_store import ProjectStore
from cvcutter.shared.types import (
    ExportStatus,
    MatchMethod,
    MatchSignalType,
    PrivacySetting,
    ProcessingState,
    SignalType,
    UploadStatus,
)


class JsonProjectStore(ProjectStore):
    """Persist and load project aggregate artifacts as JSON files."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize the store with the per-user app data base directory."""
        self._base_dir = Path(base_dir)
        self._projects_dir = self._base_dir / "projects"

    def save_project(self, project: ConcertProject) -> None:
        """Persist project root metadata."""
        project_file = self._project_dir(str(project.id)) / "project.json"
        self._write_json(project_file, asdict(project))

    def load_project(self, project_id: str) -> ConcertProject | None:
        """Load project root metadata, returning None when missing or invalid."""
        payload = self._read_json(self._project_dir(project_id) / "project.json")
        if not isinstance(payload, dict):
            return None
        return self._project_from_raw(payload)

    def save_segments(self, project_id: str, segments: list[PerformanceSegment]) -> None:
        """Persist performance segments."""
        self._write_json(
            self._project_dir(project_id) / "segments.json",
            [asdict(segment) for segment in segments],
        )

    def load_segments(self, project_id: str) -> list[PerformanceSegment]:
        """Load performance segments, returning an empty list when unavailable."""
        payload = self._read_json(self._project_dir(project_id) / "segments.json")
        if not isinstance(payload, list):
            return []

        segments: list[PerformanceSegment] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            segment = self._segment_from_raw(item)
            if segment is not None:
                segments.append(segment)
        return segments

    def save_mappings(self, project_id: str, mappings: list[VideoMetadataMapping]) -> None:
        """Persist metadata mappings."""
        self._write_json(
            self._project_dir(project_id) / "mappings.json",
            [asdict(mapping) for mapping in mappings],
        )

    def load_mappings(self, project_id: str) -> list[VideoMetadataMapping]:
        """Load metadata mappings, returning an empty list when unavailable."""
        payload = self._read_json(self._project_dir(project_id) / "mappings.json")
        if not isinstance(payload, list):
            return []

        mappings: list[VideoMetadataMapping] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            mapping = self._mapping_from_raw(item)
            if mapping is not None:
                mappings.append(mapping)
        return mappings

    def save_upload_records(self, project_id: str, uploads: list[UploadRecord]) -> None:
        """Persist upload records."""
        self._write_json(
            self._project_dir(project_id) / "uploads.json",
            [asdict(upload) for upload in uploads],
        )

    def load_upload_records(self, project_id: str) -> list[UploadRecord]:
        """Load upload records, returning an empty list when unavailable."""
        payload = self._read_json(self._project_dir(project_id) / "uploads.json")
        if not isinstance(payload, list):
            return []

        uploads: list[UploadRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            upload = self._upload_from_raw(item)
            if upload is not None:
                uploads.append(upload)
        return uploads

    def save_program_entries(self, project_id: str, entries: list[ProgramEntry]) -> None:
        """Persist parsed and enriched program entries."""
        self._write_json(
            self._project_dir(project_id) / "program_entries.json",
            [asdict(entry) for entry in entries],
        )

    def load_program_entries(self, project_id: str) -> list[ProgramEntry]:
        """Load parsed and enriched program entries."""
        payload = self._read_json(self._project_dir(project_id) / "program_entries.json")
        if not isinstance(payload, list):
            return []

        entries: list[ProgramEntry] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            entry = self._program_entry_from_raw(item)
            if entry is not None:
                entries.append(entry)
        return entries

    def save_form_responses(self, project_id: str, responses: list[FormResponse]) -> None:
        """Persist ingested form responses."""
        self._write_json(
            self._project_dir(project_id) / "form_responses.json",
            [asdict(response) for response in responses],
        )

    def load_form_responses(self, project_id: str) -> list[FormResponse]:
        """Load ingested form responses."""
        payload = self._read_json(self._project_dir(project_id) / "form_responses.json")
        if not isinstance(payload, list):
            return []

        responses: list[FormResponse] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            response = self._form_response_from_raw(item)
            if response is not None:
                responses.append(response)
        return responses

    def _project_dir(self, project_id: str) -> Path:
        """Return the directory path for a project."""
        return self._projects_dir / project_id

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse a datetime from persisted JSON-friendly values."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        """Parse a date from persisted JSON-friendly values."""
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_path(value: Any) -> Path | None:
        """Parse an optional path from persisted JSON values."""
        if isinstance(value, Path):
            return value
        if isinstance(value, str) and value:
            return Path(value)
        return None

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        """Convert optional persisted values into normalized optional text."""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _config_from_raw(raw: Any) -> ProjectConfig:
        """Build ProjectConfig from raw JSON payload with safe fallback."""
        if isinstance(raw, dict):
            try:
                return ProjectConfig(**raw)
            except (TypeError, ValueError):
                return ProjectConfig()
        return ProjectConfig()

    def _source_video_from_raw(self, raw: dict[str, Any]) -> SourceVideo | None:
        """Build SourceVideo from raw JSON payload."""
        try:
            resolution = raw.get("resolution")
            if not isinstance(resolution, (list, tuple)) or len(resolution) != 2:
                return None

            file_path = self._parse_path(raw.get("file_path"))
            if file_path is None:
                return None

            creation_timestamp = self._parse_datetime(raw.get("creation_timestamp"))
            return SourceVideo(
                id=str(raw.get("id", "")),
                file_path=file_path,
                order_index=int(raw.get("order_index", 0)),
                duration_seconds=float(raw.get("duration_seconds", 0.0)),
                resolution=(int(resolution[0]), int(resolution[1])),
                codec=str(raw.get("codec", "")),
                creation_timestamp=creation_timestamp,
                file_hash=str(raw.get("file_hash", "")),
                file_size_bytes=int(raw.get("file_size_bytes", 0)),
            )
        except (TypeError, ValueError):
            return None

    def _external_audio_from_raw(self, raw: dict[str, Any]) -> ExternalAudio | None:
        """Build ExternalAudio from raw JSON payload."""
        try:
            file_path = self._parse_path(raw.get("file_path"))
            if file_path is None:
                return None

            sync_offset_raw = raw.get("sync_offset_seconds")
            sync_offset = None if sync_offset_raw is None else float(sync_offset_raw)

            return ExternalAudio(
                id=str(raw.get("id", "")),
                file_path=file_path,
                duration_seconds=float(raw.get("duration_seconds", 0.0)),
                format=str(raw.get("format", "")),
                sample_rate=int(raw.get("sample_rate", 0)),
                file_hash=str(raw.get("file_hash", "")),
                sync_offset_seconds=sync_offset,
            )
        except (TypeError, ValueError):
            return None

    def _project_from_raw(self, raw: dict[str, Any]) -> ConcertProject | None:
        """Build ConcertProject from raw JSON payload."""
        source_videos_payload = raw.get("source_videos")
        if not isinstance(source_videos_payload, list):
            return None

        source_videos: list[SourceVideo] = []
        for item in source_videos_payload:
            if not isinstance(item, dict):
                continue
            source_video = self._source_video_from_raw(item)
            if source_video is not None:
                source_videos.append(source_video)

        external_audio: ExternalAudio | None = None
        external_audio_payload = raw.get("external_audio")
        if isinstance(external_audio_payload, dict):
            external_audio = self._external_audio_from_raw(external_audio_payload)

        try:
            project_id = UUID(str(raw.get("id")))
            created_at = self._parse_datetime(raw.get("created_at")) or datetime.now(UTC)
            updated_at = self._parse_datetime(raw.get("updated_at")) or created_at
            processing_state = ProcessingState(
                str(raw.get("processing_state", ProcessingState.CREATED.value)),
            )
            output_directory = self._parse_path(raw.get("output_directory")) or Path(".")

            return ConcertProject(
                id=project_id,
                name=str(raw.get("name", "")),
                event_date=self._parse_date(raw.get("event_date")),
                venue=self._optional_text(raw.get("venue")),
                source_videos=source_videos,
                external_audio=external_audio,
                program_pdf_path=self._parse_path(raw.get("program_pdf_path")),
                form_source_path=self._parse_path(raw.get("form_source_path")),
                form_remote_id=self._optional_text(raw.get("form_remote_id")),
                form_remote_sheet_id=self._optional_text(raw.get("form_remote_sheet_id")),
                output_directory=output_directory,
                config_snapshot=self._config_from_raw(raw.get("config_snapshot")),
                processing_state=processing_state,
                created_at=created_at,
                updated_at=updated_at,
            )
        except (TypeError, ValueError):
            return None

    def _detection_signal_from_raw(self, raw: dict[str, Any]) -> DetectionSignal | None:
        """Build DetectionSignal from raw JSON payload."""
        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        try:
            return DetectionSignal(
                signal_type=SignalType(
                    str(raw.get("signal_type", SignalType.VISUAL_YOLO.value)),
                ),
                confidence=float(raw.get("confidence", 0.0)),
                start_time_seconds=float(raw.get("start_time_seconds", 0.0)),
                end_time_seconds=float(raw.get("end_time_seconds", 0.0)),
                metadata=metadata,
            )
        except (TypeError, ValueError):
            return None

    def _segment_from_raw(self, raw: dict[str, Any]) -> PerformanceSegment | None:
        """Build PerformanceSegment from raw JSON payload."""
        raw_signals = raw.get("detection_signals")
        signals: list[DetectionSignal] = []
        if isinstance(raw_signals, list):
            for raw_signal in raw_signals:
                if not isinstance(raw_signal, dict):
                    continue
                signal = self._detection_signal_from_raw(raw_signal)
                if signal is not None:
                    signals.append(signal)

        try:
            return PerformanceSegment(
                id=UUID(str(raw.get("id"))),
                segment_index=int(raw.get("segment_index", 0)),
                start_time_seconds=float(raw.get("start_time_seconds", 0.0)),
                end_time_seconds=float(raw.get("end_time_seconds", 0.0)),
                detection_confidence=float(raw.get("detection_confidence", 0.0)),
                effective_detection_mode=str(raw.get("effective_detection_mode", "full")),
                detection_signals=signals,
                fallback_reason=self._optional_text(raw.get("fallback_reason")),
                exported_file_path=self._parse_path(raw.get("exported_file_path")),
                export_status=ExportStatus(
                    str(raw.get("export_status", ExportStatus.NOT_EXPORTED.value)),
                ),
                user_adjusted=bool(raw.get("user_adjusted", False)),
            )
        except (TypeError, ValueError):
            return None

    def _match_signal_from_raw(self, raw: dict[str, Any]) -> MatchSignal | None:
        """Build MatchSignal from raw JSON payload."""
        try:
            return MatchSignal(
                signal_type=MatchSignalType(
                    str(raw.get("signal_type", MatchSignalType.SEQUENTIAL_ORDER.value)),
                ),
                confidence=float(raw.get("confidence", 0.0)),
                evidence=str(raw.get("evidence", "")),
            )
        except (TypeError, ValueError):
            return None

    def _mapping_from_raw(self, raw: dict[str, Any]) -> VideoMetadataMapping | None:
        """Build VideoMetadataMapping from raw JSON payload."""
        raw_signals = raw.get("match_signals")
        match_signals: list[MatchSignal] = []
        if isinstance(raw_signals, list):
            for raw_signal in raw_signals:
                if not isinstance(raw_signal, dict):
                    continue
                signal = self._match_signal_from_raw(raw_signal)
                if signal is not None:
                    match_signals.append(signal)

        final_tags_raw = raw.get("final_tags")
        final_tags = [str(tag) for tag in final_tags_raw] if isinstance(final_tags_raw, list) else []

        try:
            return VideoMetadataMapping(
                id=UUID(str(raw.get("id"))),
                segment_id=str(raw.get("segment_id", "")),
                program_entry_id=self._optional_text(raw.get("program_entry_id")),
                form_response_id=self._optional_text(raw.get("form_response_id")),
                match_confidence=float(raw.get("match_confidence", 0.0)),
                match_method=MatchMethod(str(raw.get("match_method", MatchMethod.SEQUENTIAL.value))),
                match_signals=match_signals,
                user_verified=bool(raw.get("user_verified", False)),
                final_title=str(raw.get("final_title", "")),
                final_description=str(raw.get("final_description", "")),
                final_privacy=PrivacySetting(
                    str(raw.get("final_privacy", PrivacySetting.PUBLIC.value)),
                ),
                final_category_id=str(raw.get("final_category_id", "10")),
                final_tags=final_tags,
            )
        except (TypeError, ValueError):
            return None

    def _program_entry_from_raw(self, raw: dict[str, Any]) -> ProgramEntry | None:
        """Build ProgramEntry from raw JSON payload."""
        performer_names_raw = raw.get("performer_names")
        performer_names = (
            [str(name) for name in performer_names_raw]
            if isinstance(performer_names_raw, list)
            else []
        )

        try:
            return ProgramEntry(
                id=str(raw.get("id", "")),
                order_number=int(raw.get("order_number", 0)),
                piece_title=str(raw.get("piece_title", "")),
                composer=self._optional_text(raw.get("composer")),
                performer_names=performer_names,
                ensemble=self._optional_text(raw.get("ensemble")),
                instrument=self._optional_text(raw.get("instrument")),
                raw_text=str(raw.get("raw_text", "")),
            )
        except (TypeError, ValueError):
            return None

    def _form_response_from_raw(self, raw: dict[str, Any]) -> FormResponse | None:
        """Build FormResponse from raw JSON payload."""
        raw_data = raw.get("raw_data")
        normalized_raw_data: dict[str, str] = {}
        if isinstance(raw_data, dict):
            normalized_raw_data = {str(key): str(value) for key, value in raw_data.items()}

        try:
            return FormResponse(
                id=str(raw.get("id", "")),
                performer_name=str(raw.get("performer_name", "")),
                piece_title=str(raw.get("piece_title", "")),
                privacy_preference=PrivacySetting(
                    str(raw.get("privacy_preference", PrivacySetting.PUBLIC.value)),
                ),
                display_name_override=self._optional_text(raw.get("display_name_override")),
                custom_description=self._optional_text(raw.get("custom_description")),
                raw_data=normalized_raw_data,
            )
        except (TypeError, ValueError):
            return None

    def _upload_from_raw(self, raw: dict[str, Any]) -> UploadRecord | None:
        """Build UploadRecord from raw JSON payload."""
        try:
            return UploadRecord(
                id=str(raw.get("id", "")),
                segment_id=str(raw.get("segment_id", "")),
                mapping_id=str(raw.get("mapping_id", "")),
                youtube_video_id=self._optional_text(raw.get("youtube_video_id")),
                upload_status=UploadStatus(
                    str(raw.get("upload_status", UploadStatus.PENDING.value)),
                ),
                privacy_setting=PrivacySetting(
                    str(raw.get("privacy_setting", PrivacySetting.PUBLIC.value)),
                ),
                playlist_id=self._optional_text(raw.get("playlist_id")),
                quota_cost=int(raw.get("quota_cost", 1600)),
                retry_count=int(raw.get("retry_count", 0)),
                error_detail=self._optional_text(raw.get("error_detail")),
                resumable_upload_uri=self._optional_text(raw.get("resumable_upload_uri")),
                bytes_uploaded=int(raw.get("bytes_uploaded", 0)),
                failure_kind=self._optional_text(raw.get("failure_kind")),
                session_invalidated_at_utc=self._parse_datetime(raw.get("session_invalidated_at_utc")),
                restart_from_zero=bool(raw.get("restart_from_zero", False)),
                youtube_url=self._optional_text(raw.get("youtube_url")),
                uploaded_at=self._parse_datetime(raw.get("uploaded_at")),
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        """Safely write JSON data to disk."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError):
            return

    @staticmethod
    def _read_json(path: Path) -> Any | None:
        """Safely read JSON data from disk."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
