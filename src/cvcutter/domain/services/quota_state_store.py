"""Protocol for global upload quota persistence.

This store encapsulates reads/writes for global quota state shared across
projects and upload sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cvcutter.domain.models.upload import QuotaState


@runtime_checkable
class QuotaStateStore(Protocol):
    """Port for loading and saving global quota state."""

    def load(self) -> QuotaState | None:
        """Load global quota state from persistence."""
        ...

    def save(self, state: QuotaState) -> None:
        """Persist global quota state."""
        ...

