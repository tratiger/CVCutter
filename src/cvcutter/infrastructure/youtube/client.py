"""YouTube upload adapter implementing the UploadService protocol."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cvcutter.domain.services.types import UploadResult
from cvcutter.domain.services.upload_service import UploadService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from cvcutter.domain.services.credential_store import CredentialStore
    from cvcutter.domain.services.types import UploadMetadata
    from cvcutter.infrastructure.youtube.auth import YouTubeAuth
    from cvcutter.shared.types import PrivacySetting

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
except ImportError:  # pragma: no cover - dependency availability is runtime-environment specific.
    build = None  # type: ignore[assignment]
    HttpError = Exception  # type: ignore[assignment,misc]
    MediaFileUpload = None  # type: ignore[assignment]


class YouTubeClient(UploadService):
    """Google YouTube Data API v3 adapter with resumable upload semantics."""

    def __init__(
        self,
        *,
        auth: YouTubeAuth | None = None,
        credential_store: CredentialStore | None = None,
        service: Any | None = None,
        chunk_size: int = 5_242_880,
    ) -> None:
        self._auth = auth
        self._credential_store = credential_store
        self._service = service
        self._chunk_size = max(256 * 1024, int(chunk_size))

    def authenticate(self) -> bool:
        """Authenticate via OAuth and initialize the YouTube API service."""
        if self._service is not None:
            return True
        if self._auth is None or self._credential_store is None:
            return False
        if build is None:
            return False

        try:
            credentials = self._auth.authenticate(self._credential_store)
            self._service = build(
                "youtube",
                "v3",
                credentials=credentials,
                static_discovery=False,
            )
            return True
        except Exception:
            return False

    def upload(
        self,
        file_path: Path,
        metadata: UploadMetadata,
        progress_callback: Callable[[int, int], None] | None = None,
        resumable_uri: str | None = None,
        bytes_uploaded: int = 0,
        session_callback: Callable[[str], None] | None = None,
    ) -> UploadResult:
        """Upload a video file using resumable chunks and classified failure details."""
        service = self._require_service()
        if MediaFileUpload is None:
            return self._failure_result(
                resumable_uri=resumable_uri,
                bytes_uploaded=bytes_uploaded,
                failure_kind="UNKNOWN",
                error_message="googleapiclient is unavailable.",
            )

        total_bytes = file_path.stat().st_size if file_path.exists() else max(bytes_uploaded, 0)
        media = MediaFileUpload(str(file_path), chunksize=self._chunk_size, resumable=True)
        request = service.videos().insert(
            part="snippet,status",
            body=self._video_body(metadata),
            media_body=media,
        )
        if resumable_uri:
            self._set_resumable_uri(request, resumable_uri)

        active_resumable_uri = self._extract_resumable_uri(request) or resumable_uri
        if active_resumable_uri and session_callback is not None:
            session_callback(active_resumable_uri)

        acknowledged_bytes = max(0, bytes_uploaded)
        try:
            response: dict[str, Any] | None = None
            while response is None:
                status, response = request.next_chunk()
                refreshed_uri = self._extract_resumable_uri(request)
                if refreshed_uri and refreshed_uri != active_resumable_uri:
                    active_resumable_uri = refreshed_uri
                    if session_callback is not None:
                        session_callback(refreshed_uri)

                if status is not None and callable(getattr(status, "progress", None)):
                    acknowledged = int(float(status.progress()) * total_bytes)
                    acknowledged_bytes = max(acknowledged_bytes, acknowledged)
                    if progress_callback is not None:
                        progress_callback(acknowledged_bytes, total_bytes)

            video_id = self._optional_text(response.get("id"))
            if video_id is None:
                return self._failure_result(
                    resumable_uri=active_resumable_uri,
                    bytes_uploaded=acknowledged_bytes,
                    failure_kind="UNKNOWN",
                    error_message="Upload response did not include a video ID.",
                )
            return UploadResult(
                success=True,
                video_id=video_id,
                resumable_uri=active_resumable_uri,
                bytes_uploaded=max(acknowledged_bytes, total_bytes),
                failure_kind=None,
                resume_allowed=False,
                restart_from_zero=False,
                session_invalidated_at_utc=None,
                error_message=None,
            )
        except HttpError as exc:
            return self._classify_http_error(
                exc,
                resumable_uri=active_resumable_uri,
                bytes_uploaded=acknowledged_bytes,
                had_resume_state=resumable_uri is not None or bytes_uploaded > 0,
            )
        except (ConnectionError, TimeoutError) as exc:
            return self._failure_result(
                resumable_uri=active_resumable_uri,
                bytes_uploaded=acknowledged_bytes,
                failure_kind="NETWORK_TRANSIENT",
                error_message=str(exc),
                resume_allowed=True,
            )
        except OSError as exc:
            return self._failure_result(
                resumable_uri=active_resumable_uri,
                bytes_uploaded=acknowledged_bytes,
                failure_kind="UNKNOWN",
                error_message=str(exc),
                resume_allowed=False,
            )
        except Exception as exc:
            return self._failure_result(
                resumable_uri=active_resumable_uri,
                bytes_uploaded=acknowledged_bytes,
                failure_kind="UNKNOWN",
                error_message=str(exc),
                resume_allowed=True,
            )

    def create_playlist(
        self,
        title: str,
        description: str = "",
        privacy: PrivacySetting | str = "PUBLIC",
    ) -> str:
        """Create a playlist and return the resulting playlist ID."""
        service = self._require_service()
        try:
            response = service.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": title,
                        "description": description,
                    },
                    "status": {
                        "privacyStatus": self._privacy_value(privacy),
                    },
                },
            ).execute()
        except HttpError as exc:
            reason = self._http_error_reason(exc) or str(exc)
            raise RuntimeError(f"Playlist creation failed: {reason}") from exc
        playlist_id = self._optional_text(response.get("id"))
        if playlist_id is None:
            raise RuntimeError("Playlist creation response did not include an ID.")
        return playlist_id

    def add_to_playlist(self, playlist_id: str, video_id: str) -> None:
        """Add a video to an existing playlist."""
        service = self._require_service()
        try:
            service.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id,
                        },
                    },
                },
            ).execute()
        except HttpError as exc:
            reason = self._http_error_reason(exc) or str(exc)
            raise RuntimeError(f"Playlist insertion failed: {reason}") from exc

    @staticmethod
    def _video_body(metadata: UploadMetadata) -> dict[str, Any]:
        """Build API request payload from normalized upload metadata."""
        return {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": list(metadata.tags),
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": metadata.privacy_status.value.lower(),
                "selfDeclaredMadeForKids": False,
            },
        }

    @staticmethod
    def _extract_resumable_uri(request: Any) -> str | None:
        """Read resumable URI from request objects with varying internal names."""
        for attribute in ("resumable_uri", "_resumable_uri"):
            value = getattr(request, attribute, None)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _set_resumable_uri(request: Any, resumable_uri: str) -> None:
        """Apply resume URI to request objects with varying internal names."""
        for attribute in ("resumable_uri", "_resumable_uri"):
            if hasattr(request, attribute):
                setattr(request, attribute, resumable_uri)

    def _classify_http_error(
        self,
        error: Exception,
        *,
        resumable_uri: str | None,
        bytes_uploaded: int,
        had_resume_state: bool,
    ) -> UploadResult:
        """Map HTTP errors into contract-defined failure kinds and retry semantics."""
        status = int(getattr(getattr(error, "resp", None), "status", 0) or 0)
        reason = self._http_error_reason(error)
        lower_reason = reason.lower()
        lower_message = str(error).lower()
        quota_markers = (
            "quotaexceeded",
            "dailylimitexceeded",
            "userratelimitexceeded",
            "ratelimitexceeded",
        )

        if status == 403 and (
            any(marker in lower_reason for marker in quota_markers) or "quota" in lower_message
        ):
            return self._failure_result(
                resumable_uri=resumable_uri,
                bytes_uploaded=bytes_uploaded,
                failure_kind="QUOTA_EXHAUSTED",
                error_message=str(error),
                resume_allowed=True,
            )

        if status == 404 and had_resume_state:
            return self._failure_result(
                resumable_uri=None,
                bytes_uploaded=0,
                failure_kind="SESSION_INVALIDATED",
                error_message=str(error),
                resume_allowed=False,
                restart_from_zero=True,
                session_invalidated_at_utc=datetime.now(UTC),
            )

        if status == 401:
            return self._failure_result(
                resumable_uri=resumable_uri,
                bytes_uploaded=bytes_uploaded,
                failure_kind="AUTH_FAILURE",
                error_message=str(error),
                resume_allowed=False,
            )

        if status == 403 and (
            "auth" in lower_reason
            or "credential" in lower_reason
            or "insufficientpermissions" in lower_reason
            or "authorizationrequired" in lower_reason
            or "loginrequired" in lower_reason
        ):
            return self._failure_result(
                resumable_uri=resumable_uri,
                bytes_uploaded=bytes_uploaded,
                failure_kind="AUTH_FAILURE",
                error_message=str(error),
                resume_allowed=False,
            )

        if status in {500, 502, 503, 504}:
            return self._failure_result(
                resumable_uri=resumable_uri,
                bytes_uploaded=bytes_uploaded,
                failure_kind="NETWORK_TRANSIENT",
                error_message=str(error),
                resume_allowed=True,
            )

        return self._failure_result(
            resumable_uri=resumable_uri,
            bytes_uploaded=bytes_uploaded,
            failure_kind="UNKNOWN",
            error_message=str(error),
            resume_allowed=True,
        )

    @staticmethod
    def _http_error_reason(error: Exception) -> str:
        """Extract structured reason text from API HTTP error content."""
        content = getattr(error, "content", None)
        if not isinstance(content, (bytes, bytearray)):
            return ""

        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ""

        error_block = payload.get("error")
        if not isinstance(error_block, dict):
            return ""
        errors = error_block.get("errors")
        if not isinstance(errors, list):
            return ""
        for item in errors:
            if not isinstance(item, dict):
                continue
            reason = item.get("reason")
            if isinstance(reason, str) and reason:
                return reason
        return ""

    @staticmethod
    def _failure_result(
        *,
        resumable_uri: str | None,
        bytes_uploaded: int,
        failure_kind: str,
        error_message: str | None,
        resume_allowed: bool = False,
        restart_from_zero: bool = False,
        session_invalidated_at_utc: datetime | None = None,
    ) -> UploadResult:
        """Create a normalized failure UploadResult payload."""
        return UploadResult(
            success=False,
            video_id=None,
            resumable_uri=resumable_uri,
            bytes_uploaded=max(0, bytes_uploaded),
            failure_kind=failure_kind,
            resume_allowed=resume_allowed,
            restart_from_zero=restart_from_zero,
            session_invalidated_at_utc=session_invalidated_at_utc,
            error_message=error_message,
        )

    @staticmethod
    def _privacy_value(privacy: PrivacySetting | str) -> str:
        """Normalize privacy enum/string values to API lowercase tokens."""
        value = str(privacy) if isinstance(privacy, str) else privacy.value
        normalized = value.strip().lower()
        if normalized in {"public", "private", "unlisted"}:
            return normalized
        return "private"

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        """Normalize optional text values."""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _require_service(self) -> Any:
        """Return an authenticated API service or raise when unavailable."""
        if self._service is None and not self.authenticate():
            raise RuntimeError("YouTube client is not authenticated.")
        if self._service is None:
            raise RuntimeError("YouTube client service is unavailable.")
        return self._service
