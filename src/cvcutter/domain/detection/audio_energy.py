"""Audio-energy based segment activity detection and boundary extraction."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

from cvcutter.domain.models.segment import DetectionSignal
from cvcutter.shared.types import SignalType


class AudioEnergyDetector:
    """Detect candidate performance activity using calibrated RMS energy and silence gaps."""

    def __init__(
        self,
        silence_threshold: float = 0.02,
        min_silence_seconds: float = 3.0,
        frame_length: int = 2048,
        hop_length: int = 512,
        adaptive_floor_percentile: float = 20.0,
        threshold_scale: float = 1.5,
        smoothing_frames: int = 5,
        max_silence_gap_seconds: float = 1.0,
    ) -> None:
        """Initialize detector configuration values."""
        if silence_threshold < 0:
            raise ValueError("silence_threshold must be >= 0.")
        if min_silence_seconds <= 0:
            raise ValueError("min_silence_seconds must be greater than zero.")
        if frame_length <= 0 or hop_length <= 0:
            raise ValueError("frame_length and hop_length must be greater than zero.")
        if not 0.0 <= adaptive_floor_percentile <= 100.0:
            raise ValueError("adaptive_floor_percentile must be between 0 and 100.")
        if threshold_scale <= 0:
            raise ValueError("threshold_scale must be greater than zero.")
        if smoothing_frames <= 0:
            raise ValueError("smoothing_frames must be greater than zero.")
        if max_silence_gap_seconds < 0:
            raise ValueError("max_silence_gap_seconds must be >= 0.")

        self._silence_threshold = silence_threshold
        self._min_silence_seconds = min_silence_seconds
        self._frame_length = frame_length
        self._hop_length = hop_length
        self._adaptive_floor_percentile = adaptive_floor_percentile
        self._threshold_scale = threshold_scale
        self._smoothing_frames = smoothing_frames
        self._max_silence_gap_seconds = max_silence_gap_seconds

    def detect_boundaries(
        self,
        audio_path: Path,
        sample_rate: int = 22050,
        min_duration: float = 30.0,
    ) -> list[tuple[float, float, float]]:
        """Detect segment boundaries and return `(start, end, confidence)` tuples."""
        signals = self.detect_boundaries_with_signals(
            audio_path=audio_path,
            sample_rate=sample_rate,
            min_duration=min_duration,
        )
        return [
            (
                signal.start_time_seconds,
                signal.end_time_seconds,
                signal.confidence,
            )
            for signal in signals
        ]

    def detect_boundaries_with_signals(
        self,
        audio_path: Path,
        sample_rate: int = 22050,
        min_duration: float = 30.0,
    ) -> list[DetectionSignal]:
        """Detect activity boundaries and return audio-energy detection signals."""
        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero.")
        if min_duration <= 0:
            raise ValueError("min_duration must be greater than zero.")

        source_path = Path(audio_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {source_path}")

        audio, rms = self._load_audio_and_rms(source_path, sample_rate)
        if audio.size == 0 or rms.size == 0:
            return []

        frame_times = librosa.frames_to_time(
            np.arange(rms.size),
            sr=sample_rate,
            hop_length=self._hop_length,
        )
        frame_step = self._hop_length / sample_rate
        smoothed_rms = self._smooth_energy(rms)
        threshold = self._calibrated_threshold(smoothed_rms)
        active_mask = smoothed_rms >= threshold
        active_mask = self._bridge_short_silence(active_mask, frame_step)
        active_runs = self._extract_runs(active_mask)
        active_runs = self._merge_runs_with_short_silence(active_runs, frame_times, frame_step)

        max_energy = max(float(np.max(smoothed_rms)), 1e-12)
        signals: list[DetectionSignal] = []
        for run_start, run_end in active_runs:
            start_seconds = float(frame_times[run_start])
            end_seconds = float(frame_times[run_end] + frame_step)
            if end_seconds - start_seconds < min_duration:
                continue
            run_energy = smoothed_rms[run_start : run_end + 1]
            confidence = float(np.clip(np.mean(run_energy) / max_energy, 0.0, 1.0))
            signals.append(
                DetectionSignal(
                    signal_type=SignalType.AUDIO_ENERGY,
                    confidence=confidence,
                    start_time_seconds=start_seconds,
                    end_time_seconds=end_seconds,
                    metadata={
                        "source": "AudioEnergyDetector",
                        "channel": "audio_energy",
                        "calibrated_threshold": threshold,
                    },
                ),
            )

        return signals

    def _load_audio_and_rms(self, source_path: Path, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
        """Load mono audio and return sample data with RMS frame energy."""
        try:
            audio, _ = librosa.load(str(source_path), sr=sample_rate, mono=True)
        except Exception as exc:
            raise ValueError(f"Failed to load audio file: {source_path}") from exc
        if audio.size == 0:
            return audio, np.array([], dtype=float)
        rms = librosa.feature.rms(
            y=audio,
            frame_length=self._frame_length,
            hop_length=self._hop_length,
        )[0]
        return audio, rms

    def _smooth_energy(self, rms: np.ndarray) -> np.ndarray:
        """Apply moving-average smoothing to stabilize transient spikes."""
        if rms.size == 0 or self._smoothing_frames <= 1 or rms.size < self._smoothing_frames * 2:
            return rms
        kernel = np.ones(self._smoothing_frames, dtype=float) / float(self._smoothing_frames)
        return np.convolve(rms, kernel, mode="same")

    def _calibrated_threshold(self, rms: np.ndarray) -> float:
        """Compute calibrated silence threshold for multimodal fusion compatibility."""
        if rms.size == 0:
            return self._silence_threshold
        adaptive_floor = float(np.percentile(rms, self._adaptive_floor_percentile))
        return max(self._silence_threshold, adaptive_floor * self._threshold_scale)

    def _bridge_short_silence(self, active_mask: np.ndarray, frame_step_seconds: float) -> np.ndarray:
        """Fill short internal silence gaps to reduce over-segmentation."""
        if active_mask.size == 0:
            return active_mask
        maximum_gap_seconds = self._max_silence_gap_seconds
        if maximum_gap_seconds <= 0:
            return active_mask
        max_gap_frames = int(np.floor(maximum_gap_seconds / frame_step_seconds))
        if max_gap_frames <= 0:
            return active_mask

        bridged = active_mask.copy()
        for run_start, run_end in self._extract_runs(~active_mask):
            run_length = run_end - run_start + 1
            is_internal_gap = run_start > 0 and run_end < active_mask.size - 1
            if is_internal_gap and run_length <= max_gap_frames:
                bridged[run_start : run_end + 1] = True
        return bridged

    def _merge_runs_with_short_silence(
        self,
        runs: list[tuple[int, int]],
        frame_times: np.ndarray,
        frame_step_seconds: float,
    ) -> list[tuple[int, int]]:
        """Merge runs separated by less than min_silence_seconds."""
        if not runs:
            return []

        merged: list[tuple[int, int]] = [runs[0]]
        for run_start, run_end in runs[1:]:
            previous_start, previous_end = merged[-1]
            silence_start = float(frame_times[previous_end] + frame_step_seconds)
            silence_end = float(frame_times[run_start])
            if silence_end - silence_start < self._min_silence_seconds:
                merged[-1] = (previous_start, run_end)
                continue
            merged.append((run_start, run_end))
        return merged

    @staticmethod
    def _extract_runs(mask: np.ndarray) -> list[tuple[int, int]]:
        """Extract contiguous true runs from a boolean mask."""
        runs: list[tuple[int, int]] = []
        run_start: int | None = None
        for index, value in enumerate(mask):
            if value and run_start is None:
                run_start = index
                continue
            if not value and run_start is not None:
                runs.append((run_start, index - 1))
                run_start = None
        if run_start is not None:
            runs.append((run_start, mask.size - 1))
        return runs

