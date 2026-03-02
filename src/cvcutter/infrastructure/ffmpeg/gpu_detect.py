"""GPU capability detection helpers for FFmpeg adapters."""

from __future__ import annotations

import subprocess
from typing import Any

import imageio_ffmpeg


def detect_nvenc() -> bool:
    """Return True when the local FFmpeg build exposes the NVENC encoder."""
    ffmpeg_executable = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        result = subprocess.run(
            [ffmpeg_executable, "-hide_banner", "-encoders"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return False

    if result.returncode != 0:
        return False
    return "h264_nvenc" in result.stdout.lower()


def get_gpu_info() -> dict[str, Any]:
    """Return detected GPU details and NVENC capability metadata."""
    info: dict[str, Any] = {
        "nvenc_available": detect_nvenc(),
        "gpu_name": None,
        "driver_version": None,
    }

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return info

    if result.returncode != 0 or not result.stdout.strip():
        return info

    first_line = result.stdout.strip().splitlines()[0]
    fields = [field.strip() for field in first_line.split(",")]
    if fields:
        info["gpu_name"] = fields[0] or None
    if len(fields) >= 2:
        info["driver_version"] = fields[1] or None

    return info

