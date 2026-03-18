from __future__ import annotations


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
