"""Contract tests for YouTube upload adapter behavior (T070)."""

from __future__ import annotations

import json
from dataclasses import asdict
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

import cvcutter.infrastructure.youtube.client as youtube_client_module
from cvcutter.domain.services.types import UploadMetadata, UploadResult
from cvcutter.domain.services.upload_service import UploadService
from cvcutter.infrastructure.youtube.client import YouTubeClient
from cvcutter.shared.types import PrivacySetting

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.contract


class _MediaFileUploadStub:
    """Simple MediaFileUpload test double."""

    def __init__(self, filename: str, chunksize: int, resumable: bool) -> None:
        self.filename = filename
        self.chunksize = chunksize
        self.resumable = resumable


class _StatusStub:
    """Resumable chunk status test double."""

    def __init__(self, ratio: float) -> None:
        self._ratio = ratio

    def progress(self) -> float:
        return self._ratio


class _HttpErrorStubError(Exception):
    """HttpError-compatible test double."""

    def __init__(self, status: int, reason: str) -> None:
        self.resp = SimpleNamespace(status=status)
        self.content = json.dumps(
            {"error": {"errors": [{"reason": reason}]}},
            ensure_ascii=False,
        ).encode("utf-8")
        super().__init__(f"{status}:{reason}")


class _UploadRequestStub:
    """Resumable request stub returning scripted responses."""

    def __init__(
        self,
        scripted_chunks: list[tuple[_StatusStub | None, dict[str, Any] | None] | Exception],
        *,
        resumable_uri: str | None = "session://created",
    ) -> None:
        self._scripted_chunks = list(scripted_chunks)
        self.resumable_uri = resumable_uri
        self.last_seen_uri: str | None = None

    def next_chunk(self) -> tuple[_StatusStub | None, dict[str, Any] | None]:
        self.last_seen_uri = self.resumable_uri
        next_item = self._scripted_chunks.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        status, response = next_item
        return status, response


class _ExecutableStub:
    """Stub for execute()-style API resources."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def execute(self) -> dict[str, Any]:
        return self._payload


class _VideosResourceStub:
    """videos().insert(...) resource stub."""

    def __init__(self, requests: list[_UploadRequestStub]) -> None:
        self._requests = requests
        self.insert_calls: list[dict[str, Any]] = []
        self.last_request: _UploadRequestStub | None = None

    def insert(self, part: str, body: dict[str, Any], media_body: Any) -> _UploadRequestStub:
        self.insert_calls.append({"part": part, "body": body, "media_body": media_body})
        request = self._requests.pop(0)
        self.last_request = request
        return request


class _PlaylistsResourceStub:
    """playlists().insert(...) resource stub."""

    def __init__(self) -> None:
        self.insert_calls: list[dict[str, Any]] = []

    def insert(self, part: str, body: dict[str, Any]) -> _ExecutableStub:
        self.insert_calls.append({"part": part, "body": body})
        return _ExecutableStub({"id": "playlist-1"})


class _PlaylistItemsResourceStub:
    """playlistItems().insert(...) resource stub."""

    def __init__(self) -> None:
        self.insert_calls: list[dict[str, Any]] = []

    def insert(self, part: str, body: dict[str, Any]) -> _ExecutableStub:
        self.insert_calls.append({"part": part, "body": body})
        return _ExecutableStub({})


class _YouTubeServiceStub:
    """Minimal service stub exposing YouTube API resources."""

    def __init__(self, requests: list[_UploadRequestStub]) -> None:
        self.videos_resource = _VideosResourceStub(requests)
        self.playlists_resource = _PlaylistsResourceStub()
        self.playlist_items_resource = _PlaylistItemsResourceStub()

    def videos(self) -> _VideosResourceStub:
        return self.videos_resource

    def playlists(self) -> _PlaylistsResourceStub:
        return self.playlists_resource

    def playlistItems(self) -> _PlaylistItemsResourceStub:  # noqa: N802
        return self.playlist_items_resource


def _metadata() -> UploadMetadata:
    return UploadMetadata(
        title="春の演奏会 2026",
        description="高校オーケストラ定期演奏会",
        tags=["concert", "orchestra", "school"],
        privacy_status=PrivacySetting.UNLISTED,
        category_id="10",
        playlist_id="playlist-1",
    )


def _video_file(tmp_path: Path, size_bytes: int = 2048) -> Path:
    target = tmp_path / "segment-001.mp4"
    target.write_bytes(b"x" * size_bytes)
    return target


def test_youtube_client_satisfies_upload_service_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(youtube_client_module, "MediaFileUpload", _MediaFileUploadStub)
    service = _YouTubeServiceStub(
        [_UploadRequestStub([(_StatusStub(1.0), {"id": "video-001"})])],
    )
    adapter = YouTubeClient(service=service)

    assert isinstance(adapter, UploadService)


def test_upload_returns_upload_result_with_required_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(youtube_client_module, "MediaFileUpload", _MediaFileUploadStub)
    service = _YouTubeServiceStub(
        [_UploadRequestStub([(_StatusStub(1.0), {"id": "video-101"})])],
    )
    adapter = YouTubeClient(service=service)

    result = adapter.upload(_video_file(tmp_path), _metadata())

    assert isinstance(result, UploadResult)
    assert set(asdict(result)) == {
        "success",
        "video_id",
        "resumable_uri",
        "bytes_uploaded",
        "failure_kind",
        "resume_allowed",
        "restart_from_zero",
        "session_invalidated_at_utc",
        "error_message",
    }
    assert result.success is True
    assert result.video_id == "video-101"


def test_resumable_upload_valid_session_resume_keeps_offset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(youtube_client_module, "MediaFileUpload", _MediaFileUploadStub)
    request = _UploadRequestStub([(_StatusStub(1.0), {"id": "video-resume"})], resumable_uri="session://new")
    service = _YouTubeServiceStub([request])
    adapter = YouTubeClient(service=service)

    result = adapter.upload(
        _video_file(tmp_path),
        _metadata(),
        resumable_uri="session://valid",
        bytes_uploaded=512,
    )

    assert result.success is True
    assert result.restart_from_zero is False
    assert result.resumable_uri == "session://valid"
    assert request.last_seen_uri == "session://valid"


def test_resumable_upload_invalid_session_restarts_from_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(youtube_client_module, "MediaFileUpload", _MediaFileUploadStub)
    monkeypatch.setattr(youtube_client_module, "HttpError", _HttpErrorStubError)
    request = _UploadRequestStub(
        [_HttpErrorStubError(404, "uploadNotFound")],
        resumable_uri="session://stale",
    )
    service = _YouTubeServiceStub([request])
    adapter = YouTubeClient(service=service)

    result = adapter.upload(
        _video_file(tmp_path),
        _metadata(),
        resumable_uri="session://stale",
        bytes_uploaded=1024,
    )

    assert result.success is False
    assert result.failure_kind == "SESSION_INVALIDATED"
    assert result.resume_allowed is False
    assert result.restart_from_zero is True
    assert result.bytes_uploaded == 0
    assert result.resumable_uri is None
    assert result.session_invalidated_at_utc is not None


def test_403_insufficient_permissions_classified_as_auth_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(youtube_client_module, "MediaFileUpload", _MediaFileUploadStub)
    monkeypatch.setattr(youtube_client_module, "HttpError", _HttpErrorStubError)
    request = _UploadRequestStub(
        [_HttpErrorStubError(403, "insufficientPermissions")],
        resumable_uri="session://auth",
    )
    service = _YouTubeServiceStub([request])
    adapter = YouTubeClient(service=service)

    result = adapter.upload(_video_file(tmp_path), _metadata())

    assert result.success is False
    assert result.failure_kind == "AUTH_FAILURE"
    assert result.resume_allowed is False


def test_403_daily_limit_exceeded_classified_as_quota_exhausted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(youtube_client_module, "MediaFileUpload", _MediaFileUploadStub)
    monkeypatch.setattr(youtube_client_module, "HttpError", _HttpErrorStubError)
    request = _UploadRequestStub(
        [_HttpErrorStubError(403, "dailyLimitExceeded")],
        resumable_uri="session://quota",
    )
    service = _YouTubeServiceStub([request])
    adapter = YouTubeClient(service=service)

    result = adapter.upload(_video_file(tmp_path), _metadata())

    assert result.success is False
    assert result.failure_kind == "QUOTA_EXHAUSTED"


def test_create_playlist_and_add_to_playlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(youtube_client_module, "MediaFileUpload", _MediaFileUploadStub)
    service = _YouTubeServiceStub(
        [_UploadRequestStub([(_StatusStub(1.0), {"id": "video-unused"})])],
    )
    adapter = YouTubeClient(service=service)

    playlist_id = adapter.create_playlist(
        "2026 Spring Concert",
        "Concert archive playlist",
        privacy=PrivacySetting.PRIVATE,
    )
    adapter.add_to_playlist(playlist_id, "video-xyz")

    assert playlist_id == "playlist-1"
    assert service.playlists_resource.insert_calls[0]["body"]["status"]["privacyStatus"] == "private"
    add_call = service.playlist_items_resource.insert_calls[0]["body"]["snippet"]
    assert add_call["playlistId"] == "playlist-1"
    assert add_call["resourceId"]["videoId"] == "video-xyz"


def test_fr050_metadata_completeness_passed_to_videos_insert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(youtube_client_module, "MediaFileUpload", _MediaFileUploadStub)
    service = _YouTubeServiceStub(
        [_UploadRequestStub([(_StatusStub(1.0), {"id": "video-metadata"})])],
    )
    adapter = YouTubeClient(service=service)
    metadata = _metadata()

    adapter.upload(_video_file(tmp_path), metadata)
    body = service.videos_resource.insert_calls[0]["body"]

    assert body["snippet"]["title"] == metadata.title
    assert body["snippet"]["description"] == metadata.description
    assert body["snippet"]["tags"] == metadata.tags
    assert body["snippet"]["categoryId"] == metadata.category_id
    assert body["status"]["privacyStatus"] == metadata.privacy_status.value.lower()
