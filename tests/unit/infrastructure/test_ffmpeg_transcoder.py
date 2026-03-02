"""Stub tests for the planned FFmpeg transcoder infrastructure adapter.

These are intentionally skipped until the adapter is implemented and wired.
They document expected foundational behavior for probe, concatenate, and GPU
capability checks.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from cvcutter.domain.services.types import AudioMixConfig, VideoProbeResult


@pytest.mark.skip("FFmpeg adapter not yet implemented")
def test_probe_method_returns_video_probe_result(tmp_path) -> None:
    """`probe` should return a typed VideoProbeResult DTO."""
    from cvcutter.infrastructure.ffmpeg.transcoder import FFmpegTranscoder

    source = tmp_path / "input.mp4"
    source.write_bytes(b"stub-video")
    adapter = FFmpegTranscoder()

    result = adapter.probe(source)

    assert isinstance(result, VideoProbeResult)


@pytest.mark.skip("FFmpeg adapter not yet implemented")
def test_concatenate_method_creates_output_file(tmp_path) -> None:
    """`concatenate` should generate the requested output file."""
    from cvcutter.infrastructure.ffmpeg.transcoder import FFmpegTranscoder

    first = tmp_path / "part-1.mp4"
    second = tmp_path / "part-2.mp4"
    output = tmp_path / "concatenated.mp4"
    first.write_bytes(b"stub-part-1")
    second.write_bytes(b"stub-part-2")
    adapter = FFmpegTranscoder()

    adapter.concatenate([first, second], output)

    assert output.exists()


@pytest.mark.skip("FFmpeg adapter not yet implemented")
def test_check_gpu_available_returns_bool() -> None:
    """`check_gpu_available` should return a boolean capability flag."""
    from cvcutter.infrastructure.ffmpeg.transcoder import FFmpegTranscoder

    adapter = FFmpegTranscoder()

    assert isinstance(adapter.check_gpu_available(), bool)


def test_export_segment_uses_mic_only_audio_for_silent_source(tmp_path, monkeypatch) -> None:
    """`export_segment` should avoid `[0:a]` filters when source video has no audio stream."""
    from cvcutter.infrastructure.ffmpeg.transcoder import FFmpegTranscoder

    source = tmp_path / "silent.mp4"
    mic_audio = tmp_path / "mic.wav"
    output = tmp_path / "segment.mp4"
    source.write_bytes(b"silent-video")
    mic_audio.write_bytes(b"mic-audio")
    adapter = FFmpegTranscoder(ffmpeg_executable="ffmpeg")

    monkeypatch.setattr(
        adapter,
        "probe",
        lambda _: VideoProbeResult(
            duration_seconds=1.0,
            resolution=(1920, 1080),
            codec="h264",
            frame_rate=30.0,
            file_size_bytes=source.stat().st_size,
            has_audio=False,
        ),
    )
    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(adapter, "_run_command", lambda command: captured.setdefault("command", command))

    adapter.export_segment(
        source_path=source,
        output_path=output,
        start_seconds=0.0,
        end_seconds=1.0,
        audio_mix=AudioMixConfig(
            video_volume=1.0,
            mic_volume=1.0,
            mic_audio_path=mic_audio,
            sync_offset_seconds=0.0,
        ),
    )

    command = captured["command"]
    assert "1:a" in command
    assert "[0:a]volume" not in " ".join(command)


def test_probe_handles_na_duration_value(tmp_path, monkeypatch) -> None:
    """`probe` should normalize non-numeric ffprobe duration values to 0.0."""
    from cvcutter.infrastructure.ffmpeg.transcoder import FFmpegTranscoder

    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    adapter = FFmpegTranscoder(ffmpeg_executable="ffmpeg")
    payload = {
        "format": {"duration": "N/A", "size": str(source.stat().st_size)},
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "codec_name": "h264",
                "avg_frame_rate": "30/1",
                "duration": "N/A",
            },
        ],
    }
    monkeypatch.setattr(
        adapter,
        "_run_command",
        lambda command: subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )

    result = adapter.probe(source)

    assert result.duration_seconds == 0.0


def test_probe_handles_na_size_value_with_filesystem_fallback(tmp_path, monkeypatch) -> None:
    """`probe` should fallback to filesystem size when ffprobe size is non-numeric."""
    from cvcutter.infrastructure.ffmpeg.transcoder import FFmpegTranscoder

    source = tmp_path / "input.mp4"
    source.write_bytes(b"video-content")
    adapter = FFmpegTranscoder(ffmpeg_executable="ffmpeg")
    payload = {
        "format": {"duration": "1.0", "size": "N/A"},
        "streams": [
            {
                "codec_type": "video",
                "width": 1280,
                "height": 720,
                "codec_name": "h264",
                "avg_frame_rate": "30/1",
            },
        ],
    }
    monkeypatch.setattr(
        adapter,
        "_run_command",
        lambda command: subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )

    result = adapter.probe(source)

    assert result.file_size_bytes == source.stat().st_size
