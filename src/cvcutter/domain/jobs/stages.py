from __future__ import annotations

from enum import Enum


class WorkflowStage(str, Enum):
    INGEST = "ingest"
    SEGMENT = "segment"
    SYNC = "sync"
    MAP = "map"
    PUBLISH = "publish"


class JobState(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    RESUMABLE = "resumable"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
