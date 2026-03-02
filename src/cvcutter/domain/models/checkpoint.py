"""Checkpoint entity for deterministic pipeline resume behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from cvcutter.shared.types import CheckpointStatus, PipelineStage

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class Checkpoint:
    """Pipeline checkpoint capturing deterministic replay metadata."""

    id: UUID
    project_id: str
    stage: PipelineStage
    status: CheckpointStatus
    created_at: datetime
    input_hashes: dict[str, str] = field(default_factory=dict)
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    model_versions: dict[str, str] = field(default_factory=dict)
    output_references: list[str] = field(default_factory=list)
    segment_index: int | None = None
    error_detail: str | None = None

    def __post_init__(self) -> None:
        """Validate checkpoint invariants."""
        if isinstance(self.id, str):
            self.id = UUID(self.id)
        if not self.project_id.strip():
            raise ValueError("project_id must not be empty.")
        if not self.input_hashes:
            raise ValueError("input_hashes must not be empty.")
        if not self.config_snapshot:
            raise ValueError("config_snapshot must not be empty.")
        if not self.model_versions:
            raise ValueError("model_versions must not be empty.")
        if self.segment_index is not None and self.segment_index < 0:
            raise ValueError("segment_index must be >= 0 when provided.")

    def invalidate(self) -> None:
        """Mark this checkpoint as invalidated."""
        self.status = CheckpointStatus.INVALIDATED

    def is_valid(self) -> bool:
        """Return True if the checkpoint status is VALID."""
        return self.status == CheckpointStatus.VALID
