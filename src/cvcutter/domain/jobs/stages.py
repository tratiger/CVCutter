from __future__ import annotations

from enum import Enum


class WorkflowStage(str, Enum):
    INGEST = "ingest"
    CLASSIFY = "classify"
    SEGMENT_DETECT = "segment_detect"
    SYNC = "sync"
    MAP_METADATA = "map_metadata"
    EXPORT = "export"
    PUBLISH = "publish"
    SEGMENT = "segment_detect"
    MAP = "map_metadata"


LEGACY_STAGE_VALUE_ALIASES: dict[str, str] = {
    "segment": WorkflowStage.SEGMENT_DETECT.value,
    "map": WorkflowStage.MAP_METADATA.value,
}


def normalize_stage_value(stage_value: str) -> str:
    normalized = stage_value.strip()
    return LEGACY_STAGE_VALUE_ALIASES.get(normalized, normalized)


class JobState(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    RESUMABLE = "resumable"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
