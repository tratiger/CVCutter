"""Domain-level audio synchronization utilities."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
from scipy.signal import correlate, correlation_lags


def _normalize_signal(signal: np.ndarray) -> np.ndarray:
    """Normalize a signal to zero mean and unit variance when possible."""
    centered = signal - float(np.mean(signal))
    std = float(np.std(centered))
    if std <= 1e-12:
        return centered
    return centered / std


def compute_sync_offset(
    video_audio_path: Path,
    mic_audio_path: Path,
    sample_rate: int = 22050,
) -> float:
    """Estimate microphone-to-video offset using cross-correlation.

    Positive offsets mean the microphone track leads the video track.
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be greater than zero.")

    video_path = Path(video_audio_path)
    mic_path = Path(mic_audio_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video audio file does not exist: {video_path}")
    if not mic_path.exists():
        raise FileNotFoundError(f"Mic audio file does not exist: {mic_path}")

    try:
        video_signal, _ = librosa.load(str(video_path), sr=sample_rate, mono=True)
        mic_signal, _ = librosa.load(str(mic_path), sr=sample_rate, mono=True)
    except Exception as exc:
        raise ValueError("Failed to load one or both audio files for synchronization.") from exc

    if video_signal.size == 0:
        raise ValueError("video_audio_path produced an empty signal.")
    if mic_signal.size == 0:
        raise ValueError("mic_audio_path produced an empty signal.")

    normalized_video = _normalize_signal(video_signal)
    normalized_mic = _normalize_signal(mic_signal)

    correlation = correlate(normalized_video, normalized_mic, mode="full", method="fft")
    lags = correlation_lags(normalized_video.size, normalized_mic.size, mode="full")
    peak_index = int(np.argmax(correlation))
    best_lag_samples = int(lags[peak_index])

    return float(best_lag_samples / sample_rate)

