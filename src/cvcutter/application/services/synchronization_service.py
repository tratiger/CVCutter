from __future__ import annotations

from collections.abc import Sequence

import numpy as np

_MAX_CORRELATION_SAMPLES = 1_000_000


def choose_sync_path(audio_sources: int, has_embedded_video_audio: bool = True) -> str:
    if audio_sources <= 0:
        raise ValueError("audio_sources must be >= 1")
    if audio_sources > 1:
        return "manual_sync"
    return "auto_skip" if has_embedded_video_audio else "manual_sync"


def estimate_offset_ms(
    reference_signal: Sequence[float],
    target_signal: Sequence[float],
    sample_rate: int,
) -> int:
    if sample_rate <= 0:
        raise ValueError("sample_rate must be > 0")
    reference = np.asarray(reference_signal, dtype=np.float64)
    target = np.asarray(target_signal, dtype=np.float64)
    if reference.size == 0 or target.size == 0:
        raise ValueError("signals must not be empty")
    if not np.isfinite(reference).all() or not np.isfinite(target).all():
        raise ValueError("signals must contain only finite values")

    reference_centered = reference - np.mean(reference)
    target_centered = target - np.mean(target)
    if np.linalg.norm(reference_centered) == 0 or np.linalg.norm(target_centered) == 0:
        return 0
    if reference_centered.size > _MAX_CORRELATION_SAMPLES or target_centered.size > _MAX_CORRELATION_SAMPLES:
        raise ValueError("signals_too_long_for_alignment")

    # Use FFT-based cross-correlation to keep long-signal alignment bounded.
    correlation_size = target_centered.size + reference_centered.size - 1
    target_fft = np.fft.rfft(target_centered, n=correlation_size)
    reference_fft = np.fft.rfft(reference_centered, n=correlation_size)
    correlation = np.fft.irfft(target_fft * np.conj(reference_fft), n=correlation_size)
    correlation = np.roll(correlation, reference_centered.size - 1)
    lag = int(np.argmax(correlation) - (reference_centered.size - 1))
    return int(round((lag / sample_rate) * 1000))
