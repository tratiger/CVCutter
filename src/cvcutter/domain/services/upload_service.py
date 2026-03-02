"""Protocol for hosting-platform upload operations.

Adapters implementing this port handle authentication, resumable uploads, and
playlist operations while exposing a domain-stable API surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from cvcutter.shared.types import PrivacySetting

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from cvcutter.domain.services.types import UploadMetadata, UploadResult


@runtime_checkable
class UploadService(Protocol):
    """Port for video upload workflows."""

    def authenticate(self) -> bool:
        """Authenticate against the upload service and return whether auth succeeded."""
        ...

    def upload(
        self,
        file_path: Path,
        metadata: UploadMetadata,
        progress_callback: Callable[[int, int], None] | None = None,
        resumable_uri: str | None = None,
        bytes_uploaded: int = 0,
        session_callback: Callable[[str], None] | None = None,
    ) -> UploadResult:
        """Upload a file with resumable support and provider-acknowledged progress callbacks."""
        ...

    def create_playlist(
        self,
        title: str,
        description: str = "",
        privacy: PrivacySetting = PrivacySetting.PUBLIC,
    ) -> str:
        """Create a playlist and return its provider playlist identifier."""
        ...

    def add_to_playlist(self, playlist_id: str, video_id: str) -> None:
        """Associate an uploaded video with a target playlist."""
        ...

