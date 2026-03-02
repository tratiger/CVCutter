"""Project-level domain entities for concert processing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from cvcutter.shared.types import ProcessingState

if TYPE_CHECKING:
    from pathlib import Path

_PROJECT_STATE_TRANSITIONS: dict[ProcessingState, set[ProcessingState]] = {
    ProcessingState.CREATED: {ProcessingState.CONCATENATING, ProcessingState.PAUSED, ProcessingState.FAILED},
    ProcessingState.CONCATENATING: {ProcessingState.DETECTING, ProcessingState.PAUSED, ProcessingState.FAILED},
    ProcessingState.DETECTING: {ProcessingState.SYNCING_AUDIO, ProcessingState.PAUSED, ProcessingState.FAILED},
    ProcessingState.SYNCING_AUDIO: {
        ProcessingState.READY_FOR_EXPORT,
        ProcessingState.PAUSED,
        ProcessingState.FAILED,
    },
    ProcessingState.READY_FOR_EXPORT: {
        ProcessingState.EXPORTING,
        ProcessingState.PAUSED,
        ProcessingState.FAILED,
    },
    ProcessingState.EXPORTING: {ProcessingState.MAPPING, ProcessingState.PAUSED, ProcessingState.FAILED},
    ProcessingState.MAPPING: {ProcessingState.READY_FOR_UPLOAD, ProcessingState.PAUSED, ProcessingState.FAILED},
    ProcessingState.READY_FOR_UPLOAD: {
        ProcessingState.UPLOADING,
        ProcessingState.PAUSED,
        ProcessingState.FAILED,
    },
    ProcessingState.UPLOADING: {ProcessingState.COMPLETED, ProcessingState.PAUSED, ProcessingState.FAILED},
    ProcessingState.COMPLETED: set(),
    ProcessingState.PAUSED: {
        ProcessingState.CREATED,
        ProcessingState.CONCATENATING,
        ProcessingState.DETECTING,
        ProcessingState.SYNCING_AUDIO,
        ProcessingState.READY_FOR_EXPORT,
        ProcessingState.EXPORTING,
        ProcessingState.MAPPING,
        ProcessingState.READY_FOR_UPLOAD,
        ProcessingState.UPLOADING,
        ProcessingState.FAILED,
    },
    ProcessingState.FAILED: {
        ProcessingState.CREATED,
        ProcessingState.CONCATENATING,
        ProcessingState.DETECTING,
        ProcessingState.SYNCING_AUDIO,
        ProcessingState.READY_FOR_EXPORT,
        ProcessingState.EXPORTING,
        ProcessingState.MAPPING,
        ProcessingState.READY_FOR_UPLOAD,
        ProcessingState.UPLOADING,
        ProcessingState.PAUSED,
    },
}


def _validate_uuid_text(value: str, field_name: str) -> None:
    """Validate a UUID string field."""
    try:
        UUID(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid UUID string.") from exc


def _validate_existing_file(path: Path, field_name: str) -> None:
    """Validate that a path points to an existing file."""
    if not path.exists() or not path.is_file():
        raise ValueError(f"{field_name} must point to an existing file: {path}")


@dataclass(frozen=True)
class ProjectConfig:
    """Immutable configuration snapshot used for a concert project."""

    video_audio_volume: float = 0.6
    mic_audio_volume: float = 1.5
    audio_sync_sample_rate: int = 22050
    enable_yolo_detection: bool = True
    min_segment_duration_seconds: float = 30.0
    output_format: str = "mp4"
    output_quality: str = "high"
    enable_gpu: bool = True
    enable_gemini: bool = True
    gemini_model: str = "gemini-2.5-flash"
    youtube_chunk_size: int = 5_242_880
    mapping_review_threshold: float = 0.8

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if not 0.0 <= self.video_audio_volume <= 2.0:
            raise ValueError("video_audio_volume must be between 0.0 and 2.0.")
        if not 0.0 <= self.mic_audio_volume <= 2.0:
            raise ValueError("mic_audio_volume must be between 0.0 and 2.0.")
        if self.audio_sync_sample_rate <= 0:
            raise ValueError("audio_sync_sample_rate must be positive.")
        if self.min_segment_duration_seconds <= 0:
            raise ValueError("min_segment_duration_seconds must be positive.")
        if not self.output_format.strip():
            raise ValueError("output_format must not be empty.")
        if not self.output_quality.strip():
            raise ValueError("output_quality must not be empty.")
        if not self.gemini_model.strip():
            raise ValueError("gemini_model must not be empty.")
        if self.youtube_chunk_size <= 0:
            raise ValueError("youtube_chunk_size must be positive.")
        if not 0.0 <= self.mapping_review_threshold <= 1.0:
            raise ValueError("mapping_review_threshold must be between 0.0 and 1.0.")


@dataclass
class SourceVideo:
    """Input video source metadata for an ordered project timeline."""

    id: str
    file_path: Path
    order_index: int
    duration_seconds: float
    resolution: tuple[int, int]
    codec: str
    creation_timestamp: datetime | None
    file_hash: str
    file_size_bytes: int

    def __post_init__(self) -> None:
        """Validate source-video fields."""
        _validate_uuid_text(self.id, "id")
        _validate_existing_file(self.file_path, "file_path")

        if self.order_index < 0:
            raise ValueError("order_index must be >= 0.")
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be >= 0.")
        if len(self.resolution) != 2 or self.resolution[0] <= 0 or self.resolution[1] <= 0:
            raise ValueError("resolution must be a tuple of positive (width, height).")
        if not self.codec.strip():
            raise ValueError("codec must not be empty.")
        if not self.file_hash.strip():
            raise ValueError("file_hash must not be empty.")
        if self.file_size_bytes < 0:
            raise ValueError("file_size_bytes must be >= 0.")


@dataclass
class ExternalAudio:
    """Optional external microphone audio metadata."""

    id: str
    file_path: Path
    duration_seconds: float
    format: str
    sample_rate: int
    file_hash: str
    sync_offset_seconds: float | None = None

    def __post_init__(self) -> None:
        """Validate external-audio fields."""
        _validate_uuid_text(self.id, "id")
        _validate_existing_file(self.file_path, "file_path")

        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be >= 0.")
        if not self.format.strip():
            raise ValueError("format must not be empty.")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive.")
        if not self.file_hash.strip():
            raise ValueError("file_hash must not be empty.")


@dataclass
class ConcertProject:
    """Aggregate root representing a full concert processing project."""

    id: UUID
    name: str
    event_date: date | None
    venue: str | None
    source_videos: list[SourceVideo]
    external_audio: ExternalAudio | None
    program_pdf_path: Path | None
    form_source_path: Path | None
    form_remote_id: str | None
    form_remote_sheet_id: str | None
    output_directory: Path
    config_snapshot: ProjectConfig
    processing_state: ProcessingState
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate project aggregate invariants."""
        if isinstance(self.id, str):
            self.id = UUID(self.id)
        if not self.name.strip():
            raise ValueError("name must not be empty or whitespace-only.")
        if not self.source_videos:
            raise ValueError("source_videos must contain at least one source video.")
        if self.program_pdf_path is not None and self.program_pdf_path.suffix.lower() != ".pdf":
            raise ValueError("program_pdf_path must reference a PDF file.")
        if self.form_remote_id is not None and not self.form_remote_id.strip():
            raise ValueError("form_remote_id must not be empty when provided.")
        if self.form_remote_sheet_id is not None and not self.form_remote_sheet_id.strip():
            raise ValueError("form_remote_sheet_id must not be empty when provided.")
        if self.output_directory.exists() and not self.output_directory.is_dir():
            raise ValueError("output_directory must be a directory path.")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be greater than or equal to created_at.")

    def transition_to(self, new_state: ProcessingState) -> None:
        """Transition this project to a new processing state with validation."""
        if new_state == self.processing_state:
            return

        allowed_states = _PROJECT_STATE_TRANSITIONS[self.processing_state]
        if new_state not in allowed_states:
            raise ValueError(
                f"Invalid state transition: {self.processing_state.value} -> {new_state.value}",
            )

        self.processing_state = new_state
        self.updated_at = datetime.now(UTC)
