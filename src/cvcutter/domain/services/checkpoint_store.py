"""Protocol for checkpoint persistence.

This store abstracts durable checkpoint reads/writes and invalidation operations
used by orchestration layers to resume work safely.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cvcutter.domain.models.checkpoint import Checkpoint
    from cvcutter.shared.types import PipelineStage


@runtime_checkable
class CheckpointStore(Protocol):
    """Port for checkpoint read/write operations."""

    def save(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint record."""
        ...

    def load(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None = None,
    ) -> Checkpoint | None:
        """Load a checkpoint for the specified project stage and optional segment index."""
        ...

    def load_all(self, project_id: str) -> list[Checkpoint]:
        """Load all checkpoints for a project in stage order."""
        ...

    def invalidate(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None = None,
        cascade: bool = True,
    ) -> list[str]:
        """Invalidate selected checkpoint records and return invalidated checkpoint IDs."""
        ...

    def clean_completed(self, project_id: str) -> int:
        """Clean temporary artifacts for a completed project and return cleaned file count."""
        ...

