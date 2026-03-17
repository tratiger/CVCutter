from __future__ import annotations


def choose_sync_path(audio_sources: int, has_embedded_video_audio: bool = True) -> str:
    if audio_sources <= 0:
        raise ValueError("audio_sources must be >= 1")
    if audio_sources > 1:
        return "manual_sync"
    return "auto_skip" if has_embedded_video_audio else "manual_sync"
