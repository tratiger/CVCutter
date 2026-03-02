from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class MusicMetadataDictionary:
    """Metadata describing the bundled music dictionary revision in use."""

    revision_id: str
    source_summary: str
    generated_at_utc: datetime
    entry_count: int

    def __post_init__(self) -> None:
        """Validate required dictionary metadata fields."""
        if not self.revision_id.strip():
            raise ValueError("revision_id must not be empty")
