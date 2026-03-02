"""Shared enums and common type aliases for CVCutter."""

from __future__ import annotations

from enum import StrEnum

ProjectId = str
SourceVideoId = str
ExternalAudioId = str
SegmentId = str
ProgramEntryId = str
FormResponseId = str
VideoMetadataMappingId = str
CheckpointId = str
UploadRecordId = str
DictionaryRevisionId = str
YouTubeVideoId = str
PlaylistId = str


class ProcessingState(StrEnum):
    """Represents the lifecycle state of a concert processing project."""

    CREATED = "CREATED"
    CONCATENATING = "CONCATENATING"
    DETECTING = "DETECTING"
    SYNCING_AUDIO = "SYNCING_AUDIO"
    READY_FOR_EXPORT = "READY_FOR_EXPORT"
    EXPORTING = "EXPORTING"
    MAPPING = "MAPPING"
    READY_FOR_UPLOAD = "READY_FOR_UPLOAD"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


class PipelineStage(StrEnum):
    """Identifies a concrete execution stage in the processing pipeline."""

    CONCATENATION = "CONCATENATION"
    DETECTION = "DETECTION"
    AUDIO_SYNC = "AUDIO_SYNC"
    EXPORT = "EXPORT"
    MAPPING = "MAPPING"
    UPLOAD = "UPLOAD"


class CheckpointStatus(StrEnum):
    """Tracks checkpoint validity and progress for a pipeline stage."""

    IN_PROGRESS = "IN_PROGRESS"
    VALID = "VALID"
    INVALIDATED = "INVALIDATED"


class ExportStatus(StrEnum):
    """Captures export progress for a single performance segment."""

    NOT_EXPORTED = "NOT_EXPORTED"
    EXPORTING = "EXPORTING"
    EXPORTED = "EXPORTED"
    FAILED = "FAILED"


class UploadStatus(StrEnum):
    """Describes YouTube upload state for an exported segment."""

    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    QUEUED = "QUEUED"


class PrivacySetting(StrEnum):
    """Represents YouTube visibility/privacy preferences."""

    PUBLIC = "PUBLIC"
    UNLISTED = "UNLISTED"
    PRIVATE = "PRIVATE"


class SignalType(StrEnum):
    """Enumerates signal sources used for segment boundary detection."""

    VISUAL_YOLO = "VISUAL_YOLO"
    AUDIO_ENERGY = "AUDIO_ENERGY"
    AUDIO_CLASSIFIER = "AUDIO_CLASSIFIER"


class MatchMethod(StrEnum):
    """Defines the strategy used to map segments to metadata entries."""

    SEQUENTIAL = "SEQUENTIAL"
    TRANSCRIPTION = "TRANSCRIPTION"
    LOOKUP = "LOOKUP"
    FORM = "FORM"
    MANUAL = "MANUAL"


class MatchSignalType(StrEnum):
    """Enumerates individual evidence channels used during metadata matching."""

    SEQUENTIAL_ORDER = "SEQUENTIAL_ORDER"
    TRANSCRIPTION = "TRANSCRIPTION"
    MUSIC_LOOKUP = "MUSIC_LOOKUP"
    FORM_MATCH = "FORM_MATCH"


__all__ = [
    "CheckpointId",
    "CheckpointStatus",
    "DictionaryRevisionId",
    "ExportStatus",
    "ExternalAudioId",
    "FormResponseId",
    "MatchMethod",
    "MatchSignalType",
    "PipelineStage",
    "PlaylistId",
    "PrivacySetting",
    "ProcessingState",
    "ProgramEntryId",
    "ProjectId",
    "SegmentId",
    "SignalType",
    "SourceVideoId",
    "UploadRecordId",
    "UploadStatus",
    "VideoMetadataMappingId",
    "YouTubeVideoId",
]
