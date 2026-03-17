from __future__ import annotations


SUPPORTED_FORMATS = {"mp4", "mov"}


def validate_export_format(file_format: str) -> bool:
    return file_format in SUPPORTED_FORMATS


def render_opening_title(enabled: bool, duration_seconds: int) -> dict[str, int | bool]:
    return {"enabled": enabled, "duration": duration_seconds}
