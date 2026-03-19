from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


SUPPORTED_INPUT_VIDEO_FORMATS = {"mp4", "mov", "mkv", "mts"}
SUPPORTED_INPUT_AUDIO_FORMATS = {"wav", "flac", "aac"}
SUPPORTED_OUTPUT_MEDIA_FORMATS = {"mp4"}
SUPPORTED_INPUT_FORMATS = SUPPORTED_INPUT_VIDEO_FORMATS | SUPPORTED_INPUT_AUDIO_FORMATS


def validate_input_media_format(file_format: str) -> bool:
    normalized = file_format.strip().lower()
    return normalized in SUPPORTED_INPUT_FORMATS


def validate_export_format(file_format: str) -> bool:
    normalized = file_format.strip().lower()
    return normalized in SUPPORTED_OUTPUT_MEDIA_FORMATS


def render_opening_title(enabled: bool, duration_seconds: int) -> dict[str, int | bool]:
    if duration_seconds < 0:
        raise ValueError("duration_seconds_must_be_non_negative")
    return {"enabled": enabled, "duration": duration_seconds}


def export_media_file(
    input_path: Path,
    output_path: Path,
    *,
    output_format: str = "mp4",
    title_overlay_enabled: bool = False,
    title_duration_seconds: int = 0,
) -> Path:
    normalized_format = output_format.strip().lower()
    if not validate_export_format(normalized_format):
        raise ValueError("unsupported_export_format")
    if not input_path.exists():
        raise FileNotFoundError(str(input_path))
    input_suffix = input_path.suffix.lower().removeprefix(".")
    if not validate_input_media_format(input_suffix):
        raise ValueError("unsupported_input_media_format")
    if output_path.suffix.lower() != f".{normalized_format}":
        raise ValueError("output_extension_mismatch")
    render_opening_title(title_overlay_enabled, title_duration_seconds)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if title_overlay_enabled:
        raise RuntimeError("title_overlay_not_supported")
    if input_suffix == normalized_format:
        shutil.copy2(input_path, output_path)
        return output_path
    ffmpeg_command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(output_path),
    ]
    try:
        result = subprocess.run(ffmpeg_command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise RuntimeError("export_transcode_failed") from error
    if result.returncode != 0:
        raise RuntimeError("export_transcode_failed")
    return output_path
