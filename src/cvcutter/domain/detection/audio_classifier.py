"""Domain-level audio content classification channel for multimodal detection."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import librosa
import numpy as np

from cvcutter.domain.models.segment import DetectionSignal
from cvcutter.domain.services.types import AudioChunk, ClassificationResult
from cvcutter.shared.types import SignalType

if TYPE_CHECKING:
    from cvcutter.domain.services.model_runner import (
        AudioContentClassifier as AudioClassifierRunnerProtocol,
    )

_LABEL_ALIASES = {
    "music": "music",
    "musical": "music",
    "instrumental": "music",
    "speech": "speech",
    "talk": "speech",
    "applause": "applause",
    "clapping": "applause",
    "silence": "silence",
    "noise": "silence",
}
_KNOWN_LABELS = {"music", "speech", "applause", "silence"}


class AudioContentClassifier:
    """Classify short windows of audio into semantic content signals."""

    def __init__(self, model_runner: AudioClassifierRunnerProtocol) -> None:
        self._model_runner = model_runner

    def classify_segments(
        self,
        audio_path: Path,
        sample_rate: int = 22050,
        window_seconds: float = 1.0,
    ) -> list[DetectionSignal]:
        """Classify audio windows and return merged detection signals."""
        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero.")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero.")

        source_path = Path(audio_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {source_path}")

        try:
            audio, _ = librosa.load(str(source_path), sr=sample_rate, mono=True)
        except Exception as exc:
            raise ValueError(f"Failed to load audio file: {source_path}") from exc
        if audio.size == 0:
            return []

        window_samples = max(round(window_seconds * sample_rate), 1)
        model_version = self._model_runner.model_version()
        raw_signals: list[DetectionSignal] = []

        for chunk_start in range(0, audio.size, window_samples):
            chunk_end = min(chunk_start + window_samples, audio.size)
            chunk_duration = (chunk_end - chunk_start) / sample_rate
            chunk = AudioChunk(
                data=audio[chunk_start:chunk_end].astype(np.float32, copy=False),
                sample_rate=sample_rate,
                start_seconds=chunk_start / sample_rate,
                duration_seconds=chunk_duration,
            )
            best_result = self._best_result(self._model_runner.classify(chunk))
            if best_result is None:
                continue
            label, confidence = best_result
            raw_signals.append(
                DetectionSignal(
                    signal_type=SignalType.AUDIO_CLASSIFIER,
                    confidence=confidence,
                    start_time_seconds=chunk.start_seconds,
                    end_time_seconds=chunk.start_seconds + chunk.duration_seconds,
                    metadata={
                        "label": label,
                        "source": "AudioContentClassifier",
                        "model_version": model_version,
                    },
                ),
            )

        return self._merge_adjacent(raw_signals)

    def _best_result(self, results: list[ClassificationResult]) -> tuple[str, float] | None:
        """Select the highest-confidence normalized label from model outputs."""
        best_label: str | None = None
        best_confidence = -1.0
        for result in results:
            label = self._normalize_label(result.label)
            if label is None:
                continue
            confidence = float(np.clip(result.confidence, 0.0, 1.0))
            if confidence > best_confidence:
                best_confidence = confidence
                best_label = label

        if best_label is None:
            return None
        return best_label, best_confidence

    @staticmethod
    def _normalize_label(label: str) -> str | None:
        normalized = _LABEL_ALIASES.get(label.strip().lower())
        if normalized not in _KNOWN_LABELS:
            return None
        return normalized

    @staticmethod
    def _merge_adjacent(signals: list[DetectionSignal]) -> list[DetectionSignal]:
        """Merge contiguous windows with the same label into regions."""
        if not signals:
            return []

        merged: list[DetectionSignal] = []
        for signal in signals:
            if not merged:
                merged.append(signal)
                continue
            previous = merged[-1]
            same_label = previous.metadata.get("label") == signal.metadata.get("label")
            contiguous = abs(previous.end_time_seconds - signal.start_time_seconds) <= 1e-6
            if not (same_label and contiguous):
                merged.append(signal)
                continue

            previous_duration = previous.end_time_seconds - previous.start_time_seconds
            current_duration = signal.end_time_seconds - signal.start_time_seconds
            total_duration = previous_duration + current_duration
            weighted_confidence = (
                (previous.confidence * previous_duration) + (signal.confidence * current_duration)
            ) / max(total_duration, 1e-12)
            merged[-1] = DetectionSignal(
                signal_type=SignalType.AUDIO_CLASSIFIER,
                confidence=float(np.clip(weighted_confidence, 0.0, 1.0)),
                start_time_seconds=previous.start_time_seconds,
                end_time_seconds=signal.end_time_seconds,
                metadata=dict(previous.metadata),
            )
        return merged
