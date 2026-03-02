"""Unit tests for audio synchronization offset behavior (T104)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
from scipy.io import wavfile

from cvcutter.domain.audio.sync import compute_sync_offset
from tests.conftest import make_project_id

if TYPE_CHECKING:
    from pathlib import Path


def _write_wav(path: Path, signal: np.ndarray, sample_rate: int) -> None:
    clipped = np.clip(signal, -1.0, 1.0)
    wavfile.write(path, sample_rate, (clipped * 32767).astype(np.int16))


def _base_signal(sample_rate: int, *, length_seconds: float = 1.0) -> np.ndarray:
    t = np.linspace(0.0, length_seconds, int(sample_rate * length_seconds), endpoint=False)
    signal = 0.5 * np.sin(2 * np.pi * 220 * t) + 0.3 * np.sin(2 * np.pi * 440 * t)
    return signal.astype(np.float32)


def test_audio_sync_offset_calculation_with_known_test_data(tmp_path: Path) -> None:
    sample_rate = 8000
    video_signal = _base_signal(sample_rate)
    lead_samples = 120
    mic_signal = np.concatenate([video_signal[lead_samples:], np.zeros(lead_samples, dtype=np.float32)])

    video_path = tmp_path / f"video-{make_project_id()}.wav"
    mic_path = tmp_path / f"mic-{make_project_id()}.wav"
    _write_wav(video_path, video_signal, sample_rate)
    _write_wav(mic_path, mic_signal, sample_rate)

    offset_seconds = compute_sync_offset(video_path, mic_path, sample_rate=sample_rate)

    assert offset_seconds == pytest.approx(lead_samples / sample_rate, abs=0.01)


def test_audio_sync_zero_offset_with_identical_tracks(tmp_path: Path) -> None:
    sample_rate = 8000
    signal = _base_signal(sample_rate)
    video_path = tmp_path / "video.wav"
    mic_path = tmp_path / "mic.wav"
    _write_wav(video_path, signal, sample_rate)
    _write_wav(mic_path, signal, sample_rate)

    offset_seconds = compute_sync_offset(video_path, mic_path, sample_rate=sample_rate)

    assert offset_seconds == pytest.approx(0.0, abs=0.01)


def test_audio_sync_known_positive_offset(tmp_path: Path) -> None:
    sample_rate = 8000
    video_signal = _base_signal(sample_rate)
    lead_samples = 64
    mic_signal = np.concatenate([video_signal[lead_samples:], np.zeros(lead_samples, dtype=np.float32)])

    video_path = tmp_path / "video-positive.wav"
    mic_path = tmp_path / "mic-positive.wav"
    _write_wav(video_path, video_signal, sample_rate)
    _write_wav(mic_path, mic_signal, sample_rate)

    offset_seconds = compute_sync_offset(video_path, mic_path, sample_rate=sample_rate)

    assert offset_seconds > 0
    assert offset_seconds == pytest.approx(lead_samples / sample_rate, abs=0.01)


def test_audio_sync_handles_empty_or_very_short_audio_gracefully(tmp_path: Path) -> None:
    sample_rate = 8000
    empty_video = tmp_path / "empty-video.wav"
    short_mic = tmp_path / "short-mic.wav"
    short_video = tmp_path / "short-video.wav"
    short_video_clone = tmp_path / "short-video-clone.wav"

    _write_wav(empty_video, np.array([], dtype=np.float32), sample_rate)
    _write_wav(short_mic, np.array([0.1, -0.1], dtype=np.float32), sample_rate)
    _write_wav(short_video, np.array([0.1, -0.1, 0.1], dtype=np.float32), sample_rate)
    _write_wav(short_video_clone, np.array([0.1, -0.1, 0.1], dtype=np.float32), sample_rate)

    with pytest.raises(ValueError):
        compute_sync_offset(empty_video, short_mic, sample_rate=sample_rate)

    short_offset = compute_sync_offset(short_video, short_video_clone, sample_rate=sample_rate)
    assert isinstance(short_offset, float)
