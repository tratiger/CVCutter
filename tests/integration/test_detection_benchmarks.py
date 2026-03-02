"""Detection-quality benchmark scaffolding for SC-002 (T040)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from cvcutter.domain.detection.detector import CompositeDetector, DetectionFusionConfig
from cvcutter.domain.models.project import ProjectConfig
from cvcutter.domain.models.segment import DetectionSignal
from cvcutter.shared.types import SignalType

pytestmark = [pytest.mark.integration, pytest.mark.benchmark, pytest.mark.slow]


@dataclass
class _StubAudioEnergy:
    signals: list[DetectionSignal]

    def detect_boundaries_with_signals(
        self,
        audio_path: Path,
        sample_rate: int = 22050,
        min_duration: float = 30.0,
    ) -> list[DetectionSignal]:
        del audio_path, sample_rate, min_duration
        return list(self.signals)


@dataclass
class _StubAudioClassifier:
    signals: list[DetectionSignal]

    def classify_segments(
        self,
        audio_path: Path,
        sample_rate: int = 22050,
        window_seconds: float = 1.0,
    ) -> list[DetectionSignal]:
        del audio_path, sample_rate, window_seconds
        return list(self.signals)


class _UnavailableVisualDetector:
    def detect_activity(self, video_path: Path, fps: float = 1.0) -> list[DetectionSignal]:
        del video_path, fps
        raise RuntimeError("YOLO model unavailable at runtime")


def test_sc002_full_mode_quality_benchmark_scaffold() -> None:
    pytest.skip("SC-002 full-mode benchmark scaffold: target recall/boundary >=90% within ±5s.")


def test_sc002_audio_only_quality_benchmark_scaffold() -> None:
    pytest.skip("SC-002 audio-only benchmark scaffold: target >=80% within ±8s.")


def test_sc002_yolo_unavailable_runtime_fallback_emits_audio_only_provenance() -> None:
    detector = CompositeDetector(
        visual_detector=_UnavailableVisualDetector(),
        audio_energy_detector=_StubAudioEnergy(
            signals=[
                DetectionSignal(
                    signal_type=SignalType.AUDIO_ENERGY,
                    confidence=0.88,
                    start_time_seconds=0.0,
                    end_time_seconds=50.0,
                    metadata={},
                ),
            ],
        ),
        audio_classifier=_StubAudioClassifier(
            signals=[
                DetectionSignal(
                    signal_type=SignalType.AUDIO_CLASSIFIER,
                    confidence=0.8,
                    start_time_seconds=0.0,
                    end_time_seconds=50.0,
                    metadata={"label": "music"},
                ),
            ],
        ),
        config=DetectionFusionConfig(min_segment_duration_seconds=10.0),
    )

    segments = detector.detect(
        audio_path=Path("audio.wav"),
        video_path=Path("video.mp4"),
        config=ProjectConfig(enable_yolo_detection=True, min_segment_duration_seconds=10.0),
    )

    assert segments
    assert all(segment.effective_detection_mode == "audio_only" for segment in segments)
    assert all(segment.fallback_reason == "YOLO_UNAVAILABLE" for segment in segments)
    assert all(
        all(signal.signal_type != SignalType.VISUAL_YOLO for signal in segment.detection_signals)
        for segment in segments
    )
