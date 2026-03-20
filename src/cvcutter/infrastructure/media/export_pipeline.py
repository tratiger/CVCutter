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


def _build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    *,
    input_suffix: str,
    title_overlay_enabled: bool,
    title_duration_seconds: int,
) -> list[str]:
    audio_only_source = input_suffix in SUPPORTED_INPUT_AUDIO_FORMATS
    if audio_only_source:
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=1280x720:r=30",
            "-i",
            str(input_path),
            "-shortest",
        ]
    else:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
        ]
    if title_overlay_enabled:
        duration = max(0, title_duration_seconds)
        if audio_only_source:
            filter_expression = (
                "[0:v]drawtext=text='Opening Title':"
                "fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2:"
                f"enable='between(t\\,0\\,{duration})'[vout]"
            )
        else:
            filter_expression = (
                "drawtext=text='Opening Title':"
                "fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2:"
                f"enable='between(t\\,0\\,{duration})'"
            )
        command.extend(["-filter_complex", filter_expression])
    if audio_only_source:
        if title_overlay_enabled:
            command.extend(["-map", "[vout]", "-map", "1:a:0"])
        else:
            command.extend(["-map", "0:v:0", "-map", "1:a:0"])
    command.extend(["-c:v", "libx264", "-c:a", "aac", str(output_path)])
    return command


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

    if input_suffix == normalized_format and not title_overlay_enabled:
        shutil.copy2(input_path, output_path)
        return output_path

    ffmpeg_command = _build_ffmpeg_command(
        input_path,
        output_path,
        input_suffix=input_suffix,
        title_overlay_enabled=title_overlay_enabled,
        title_duration_seconds=title_duration_seconds,
    )
    try:
        result = subprocess.run(ffmpeg_command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise RuntimeError("export_transcode_failed") from error
    if result.returncode != 0:
        raise RuntimeError("export_transcode_failed")
    return output_path
