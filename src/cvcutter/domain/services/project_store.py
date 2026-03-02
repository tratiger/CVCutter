"""Protocol for persistence of project aggregate artifacts.

Adapters implementing this port handle all read/write operations for project
state documents while preserving domain-level model boundaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cvcutter.domain.models.metadata import (
        FormResponse,
        ProgramEntry,
        VideoMetadataMapping,
    )
    from cvcutter.domain.models.project import ConcertProject
    from cvcutter.domain.models.segment import PerformanceSegment
    from cvcutter.domain.models.upload import UploadRecord


@runtime_checkable
class ProjectStore(Protocol):
    """Port for reading and writing persisted project aggregate state."""

    def save_project(self, project: ConcertProject) -> None:
        """Persist project root metadata."""
        ...

    def load_project(self, project_id: str) -> ConcertProject | None:
        """Load project root metadata."""
        ...

    def save_segments(self, project_id: str, segments: list[PerformanceSegment]) -> None:
        """Persist performance segments."""
        ...

    def load_segments(self, project_id: str) -> list[PerformanceSegment]:
        """Load performance segments."""
        ...

    def save_mappings(self, project_id: str, mappings: list[VideoMetadataMapping]) -> None:
        """Persist metadata mappings."""
        ...

    def load_mappings(self, project_id: str) -> list[VideoMetadataMapping]:
        """Load metadata mappings."""
        ...

    def save_upload_records(self, project_id: str, uploads: list[UploadRecord]) -> None:
        """Persist upload records."""
        ...

    def load_upload_records(self, project_id: str) -> list[UploadRecord]:
        """Load upload records."""
        ...

    def save_program_entries(self, project_id: str, entries: list[ProgramEntry]) -> None:
        """Persist parsed/enriched program entries."""
        ...

    def load_program_entries(self, project_id: str) -> list[ProgramEntry]:
        """Load parsed/enriched program entries."""
        ...

    def save_form_responses(self, project_id: str, responses: list[FormResponse]) -> None:
        """Persist ingested form responses."""
        ...

    def load_form_responses(self, project_id: str) -> list[FormResponse]:
        """Load ingested form responses."""
        ...

