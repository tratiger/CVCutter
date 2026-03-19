from pathlib import Path

import pytest

from cvcutter.infrastructure.media.export_pipeline import (
    export_media_file,
    render_opening_title,
    validate_export_format,
    validate_input_media_format,
)


def test_format_and_title_overlay() -> None:
    assert validate_input_media_format("mkv")
    assert validate_input_media_format("mts")
    assert validate_input_media_format("wav")
    assert validate_export_format("mp4")
    assert not validate_export_format("mkv")
    assert not validate_export_format("mts")
    assert not validate_export_format("avi")
    assert render_opening_title(True, 3)["enabled"]


def test_export_media_file_copies_to_mp4_output(tmp_path: Path) -> None:
    input_path = tmp_path / "source.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake-media-bytes")

    exported = export_media_file(input_path, output_path, output_format="mp4")

    assert exported == output_path
    assert output_path.read_bytes() == b"fake-media-bytes"


def test_export_media_file_accepts_uppercase_output_format(tmp_path: Path) -> None:
    input_path = tmp_path / "source.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake-media-bytes")
    exported = export_media_file(input_path, output_path, output_format="MP4")
    assert exported == output_path


def test_export_media_file_rejects_unsupported_input_type(tmp_path: Path) -> None:
    input_path = tmp_path / "source.txt"
    output_path = tmp_path / "output.mp4"
    input_path.write_text("not media", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported_input_media_format"):
        export_media_file(input_path, output_path, output_format="mp4")


def test_export_media_file_rejects_unimplemented_title_overlay(tmp_path: Path) -> None:
    input_path = tmp_path / "source.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake-media-bytes")
    with pytest.raises(RuntimeError, match="title_overlay_not_supported"):
        export_media_file(
            input_path,
            output_path,
            output_format="mp4",
            title_overlay_enabled=True,
            title_duration_seconds=2,
        )


def test_export_media_file_transcodes_non_mp4_inputs_with_ffmpeg(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "source.wav"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake-wav-bytes")

    class _Result:
        returncode = 0

    def _fake_run(command, capture_output, text, check):
        assert command[0] == "ffmpeg"
        output_path.write_bytes(b"fake-transcoded-mp4")
        return _Result()

    monkeypatch.setattr("cvcutter.infrastructure.media.export_pipeline.subprocess.run", _fake_run)
    exported = export_media_file(input_path, output_path, output_format="mp4")
    assert exported == output_path
    assert output_path.read_bytes() == b"fake-transcoded-mp4"


def test_export_media_file_ffmpeg_command_has_no_overlay_filters_when_disabled(
    monkeypatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "source.wav"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake-wav-bytes")
    observed: dict[str, list[str]] = {"command": []}

    class _Result:
        returncode = 0

    def _fake_run(command, capture_output, text, check):
        observed["command"] = list(command)
        output_path.write_bytes(b"fake-transcoded-mp4")
        return _Result()

    monkeypatch.setattr("cvcutter.infrastructure.media.export_pipeline.subprocess.run", _fake_run)
    export_media_file(input_path, output_path, output_format="mp4", title_overlay_enabled=False)
    assert "-filter_complex" not in observed["command"]


def test_export_media_file_raises_when_ffmpeg_transcode_fails(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "source.wav"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake-wav-bytes")

    class _Result:
        returncode = 1

    monkeypatch.setattr(
        "cvcutter.infrastructure.media.export_pipeline.subprocess.run",
        lambda *args, **kwargs: _Result(),
    )
    with pytest.raises(RuntimeError, match="export_transcode_failed"):
        export_media_file(input_path, output_path, output_format="mp4")
