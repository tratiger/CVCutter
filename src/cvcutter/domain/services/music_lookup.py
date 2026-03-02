"""Protocol for local music dictionary lookup.

This port represents read-only dictionary matching that supports metadata
mapping without requiring runtime network access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cvcutter.domain.services.types import MusicLookupMatch


@runtime_checkable
class MusicLookupService(Protocol):
    """Port for local bundled dictionary lookup with graceful degradation."""

    def lookup(
        self,
        title: str,
        composer: str | None = None,
        performers: list[str] | None = None,
    ) -> list[MusicLookupMatch]:
        """Return scored dictionary matches; return [] when lookup is unavailable."""
        ...

    def is_available(self) -> bool:
        """Check whether dictionary data is readable and usable."""
        ...

    def dictionary_revision(self) -> str:
        """Return dictionary revision identifier for reproducibility and auditing."""
        ...

