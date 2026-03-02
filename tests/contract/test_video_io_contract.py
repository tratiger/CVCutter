"""Contract tests for the FFmpeg VideoIO adapter (T023)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cvcutter.domain.services.types import VideoProbeResult
from cvcutter.domain.services.video_io import VideoIOService

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.contract


def _ffmpeg_transcoder_type() -> type:
    module = pytest.importorskip(
        "cvcutter.infrastructure.ffmpeg.transcoder",
        reason="FFmpeg adapter not yet implemented",
    )
    return module.FFmpegTranscoder


def test_ffmpeg_transcoder_satisfies_video_io_service_protocol() -> None:
    transcoder_type = _ffmpeg_transcoder_type()
    adapter = transcoder_type()
    assert isinstance(adapter, VideoIOService)


@pytest.mark.skip("FFmpeg adapter not yet implemented")
def test_probe_returns_video_probe_result(tmp_path: Path) -> None:
    transcoder_type = _ffmpeg_transcoder_type()
    source = tmp_path / "probe-input.mp4"
    source.write_bytes(b"\x00" * 1024)

    result = transcoder_type().probe(source)

    assert isinstance(result, VideoProbeResult)


@pytest.mark.skip("FFmpeg adapter not yet implemented")
def test_concatenate_creates_output_file(tmp_path: Path) -> None:
    transcoder_type = _ffmpeg_transcoder_type()
    first = tmp_path / "part-1.mp4"
    second = tmp_path / "part-2.mp4"
    output = tmp_path / "concatenated.mp4"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    transcoder_type().concatenate([first, second], output)

    assert output.exists()


@pytest.mark.skip("FFmpeg adapter not yet implemented")
def test_export_segment_creates_segment_file(tmp_path: Path) -> None:
    transcoder_type = _ffmpeg_transcoder_type()
    source = tmp_path / "source.mp4"
    source.write_bytes(b"\x00" * 1024)
    output = tmp_path / "segment.mp4"

    transcoder_type().export_segment(source, output, 0.0, 10.0)

    assert output.exists()


@pytest.mark.skip("FFmpeg adapter not yet implemented")
def test_check_gpu_available_returns_bool() -> None:
    transcoder_type = _ffmpeg_transcoder_type()
    assert isinstance(transcoder_type().check_gpu_available(), bool)
