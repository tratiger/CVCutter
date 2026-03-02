"""Unit tests for multimodal performance detection (US3 / T038-T039)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from cvcutter.domain.detection.audio_classifier import AudioContentClassifier
from cvcutter.domain.detection.audio_energy import AudioEnergyDetector
from cvcutter.domain.detection.detector import CompositeDetector, DetectionFusionConfig
from cvcutter.domain.detection.visual_detector import VisualActivityDetector
from cvcutter.domain.models.project import ProjectConfig
from cvcutter.domain.models.segment import DetectionSignal
from cvcutter.domain.services.types import AudioChunk, ClassificationResult, Detection, VideoFrame
from cvcutter.shared.types import SignalType


@dataclass
class _StubAudioEnergyChannel:
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
class _StubAudioClassifierChannel:
    signals: list[DetectionSignal]

    def classify_segments(
        self,
        audio_path: Path,
        sample_rate: int = 22050,
        window_seconds: float = 1.0,
    ) -> list[DetectionSignal]:
        del audio_path, sample_rate, window_seconds
        return list(self.signals)


@dataclass
class _StubVisualChannel:
    signals: list[DetectionSignal]
    runtime_error: Exception | None = None

    def detect_activity(self, video_path: Path, fps: float = 1.0) -> list[DetectionSignal]:
        del video_path, fps
        if self.runtime_error is not None:
            raise self.runtime_error
        return list(self.signals)


class _FakeAudioRunner:
    def classify(self, audio_chunk: AudioChunk) -> list[ClassificationResult]:
        label_by_window = {
            0: "music",
            1: "speech",
            2: "applause",
            3: "silence",
        }
        label = label_by_window.get(int(audio_chunk.start_seconds), "silence")
        return [
            ClassificationResult(
                label=label,
                confidence=0.85 if label != "silence" else 0.7,
                start_seconds=audio_chunk.start_seconds,
                end_seconds=audio_chunk.start_seconds + audio_chunk.duration_seconds,
            ),
        ]

    def model_version(self) -> str:
        return "fake-audio-model"


class _FakeVisualRunner:
    def detect(self, frame: VideoFrame) -> list[Detection]:
        if frame.frame_index in {1, 2, 3}:
            return [
                Detection(class_name="person", confidence=0.9, bbox=(0.1, 0.1, 0.4, 0.9)),
                Detection(class_name="violin", confidence=0.8, bbox=(0.2, 0.2, 0.5, 0.8)),
            ]
        if frame.frame_index == 4:
            return [Detection(class_name="person", confidence=0.6, bbox=(0.1, 0.1, 0.4, 0.9))]
        return []

    def model_version(self) -> str:
        return "fake-yolo"


def test_audio_energy_detect_boundaries_with_signals_detects_silence_gaps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_path = tmp_path / "energy.wav"
    audio_path.write_bytes(b"\x00")
    rms_values = np.array([0.8, 0.85, 0.82, 0.03, 0.02, 0.01, 0.9, 0.88, 0.86], dtype=float)
    audio = np.zeros(9, dtype=float)

    monkeypatch.setattr(
        "cvcutter.domain.detection.audio_energy.librosa.load",
        lambda *_args, **_kwargs: (audio, 1),
    )
    monkeypatch.setattr(
        "cvcutter.domain.detection.audio_energy.librosa.feature.rms",
        lambda **_kwargs: np.array([rms_values]),
    )

    detector = AudioEnergyDetector(
        silence_threshold=0.05,
        min_silence_seconds=2.0,
        frame_length=2,
        hop_length=1,
    )
    signals = detector.detect_boundaries_with_signals(audio_path, sample_rate=1, min_duration=1.0)

    assert len(signals) == 2
    assert all(signal.signal_type == SignalType.AUDIO_ENERGY for signal in signals)
    assert signals[0].start_time_seconds == pytest.approx(0.0)
    assert signals[0].end_time_seconds <= signals[1].start_time_seconds


def test_audio_classifier_classifies_music_speech_applause_and_silence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_path = tmp_path / "classifier.wav"
    audio_path.write_bytes(b"\x00")
    monkeypatch.setattr(
        "cvcutter.domain.detection.audio_classifier.librosa.load",
        lambda *_args, **_kwargs: (np.zeros(16, dtype=float), 4),
    )

    classifier = AudioContentClassifier(model_runner=_FakeAudioRunner())
    signals = classifier.classify_segments(audio_path, sample_rate=4, window_seconds=1.0)
    labels = {str(signal.metadata.get("label")) for signal in signals}

    assert {"music", "speech", "applause", "silence"}.issubset(labels)
    assert all(signal.signal_type == SignalType.AUDIO_CLASSIFIER for signal in signals)
    assert all(0.0 <= signal.confidence <= 1.0 for signal in signals)


def test_visual_detector_tracks_person_count_and_instrument_presence() -> None:
    def frame_sampler(_video_path: Path, _fps: float) -> list[VideoFrame]:
        return [
            VideoFrame(data=np.zeros((8, 8, 3), dtype=np.uint8), timestamp_seconds=float(i), frame_index=i)
            for i in range(5)
        ]

    detector = VisualActivityDetector(
        model_runner=_FakeVisualRunner(),
        frame_sampler=frame_sampler,
    )

    signals = detector.detect_activity(Path("dummy.mp4"), fps=1.0)

    assert signals
    first = signals[0]
    assert first.signal_type == SignalType.VISUAL_YOLO
    assert first.metadata["person_count_max"] >= 1
    assert first.metadata["instrument_present"] is True


def test_composite_detector_fuses_multimodal_channels_and_splits_on_transition() -> None:
    audio_energy = _StubAudioEnergyChannel(
        signals=[
            DetectionSignal(
                signal_type=SignalType.AUDIO_ENERGY,
                confidence=0.92,
                start_time_seconds=0.0,
                end_time_seconds=25.0,
                metadata={"channel": "energy"},
            ),
            DetectionSignal(
                signal_type=SignalType.AUDIO_ENERGY,
                confidence=0.88,
                start_time_seconds=34.0,
                end_time_seconds=62.0,
                metadata={"channel": "energy"},
            ),
        ],
    )
    audio_classifier = _StubAudioClassifierChannel(
        signals=[
            DetectionSignal(
                signal_type=SignalType.AUDIO_CLASSIFIER,
                confidence=0.9,
                start_time_seconds=0.0,
                end_time_seconds=24.0,
                metadata={"label": "music"},
            ),
            DetectionSignal(
                signal_type=SignalType.AUDIO_CLASSIFIER,
                confidence=0.95,
                start_time_seconds=24.0,
                end_time_seconds=34.0,
                metadata={"label": "silence"},
            ),
            DetectionSignal(
                signal_type=SignalType.AUDIO_CLASSIFIER,
                confidence=0.82,
                start_time_seconds=34.0,
                end_time_seconds=62.0,
                metadata={"label": "applause"},
            ),
        ],
    )
    visual_detector = _StubVisualChannel(
        signals=[
            DetectionSignal(
                signal_type=SignalType.VISUAL_YOLO,
                confidence=0.7,
                start_time_seconds=0.0,
                end_time_seconds=23.0,
                metadata={"person_count_max": 8, "instrument_present": True},
            ),
            DetectionSignal(
                signal_type=SignalType.VISUAL_YOLO,
                confidence=0.78,
                start_time_seconds=35.0,
                end_time_seconds=62.0,
                metadata={"person_count_max": 7, "instrument_present": True},
            ),
        ],
    )
    detector = CompositeDetector(
        visual_detector=visual_detector,
        audio_energy_detector=audio_energy,
        audio_classifier=audio_classifier,
        config=DetectionFusionConfig(
            start_threshold=0.5,
            stop_threshold=0.35,
            transition_hold_seconds=4.0,
            min_segment_duration_seconds=10.0,
            visual_weight=0.25,
            audio_energy_weight=0.4,
            audio_classifier_weight=0.35,
        ),
    )

    segments = detector.detect(
        audio_path=Path("audio.wav"),
        video_path=Path("video.mp4"),
        config=ProjectConfig(min_segment_duration_seconds=10.0, enable_yolo_detection=True),
    )

    assert len(segments) == 2
    assert all(segment.effective_detection_mode == "full" for segment in segments)
    assert segments[0].end_time_seconds <= segments[1].start_time_seconds
    assert all(segment.detection_confidence >= 0.6 for segment in segments)
    assert all(
        {
            SignalType.AUDIO_ENERGY,
            SignalType.AUDIO_CLASSIFIER,
            SignalType.VISUAL_YOLO,
        }.issubset({signal.signal_type for signal in segment.detection_signals})
        for segment in segments
    )


def test_composite_detector_yolo_disabled_falls_back_to_audio_only() -> None:
    audio_energy = _StubAudioEnergyChannel(
        signals=[
            DetectionSignal(
                signal_type=SignalType.AUDIO_ENERGY,
                confidence=0.9,
                start_time_seconds=0.0,
                end_time_seconds=40.0,
                metadata={},
            ),
        ],
    )
    audio_classifier = _StubAudioClassifierChannel(
        signals=[
            DetectionSignal(
                signal_type=SignalType.AUDIO_CLASSIFIER,
                confidence=0.8,
                start_time_seconds=0.0,
                end_time_seconds=40.0,
                metadata={"label": "music"},
            ),
        ],
    )
    detector = CompositeDetector(
        visual_detector=_StubVisualChannel(signals=[]),
        audio_energy_detector=audio_energy,
        audio_classifier=audio_classifier,
        config=DetectionFusionConfig(min_segment_duration_seconds=10.0),
    )

    segments = detector.detect(
        audio_path=Path("audio.wav"),
        video_path=Path("video.mp4"),
        config=ProjectConfig(min_segment_duration_seconds=10.0, enable_yolo_detection=False),
    )

    assert segments
    assert all(segment.effective_detection_mode == "audio_only" for segment in segments)
    assert all(segment.fallback_reason == "YOLO_DISABLED" for segment in segments)
    assert all(
        all(signal.signal_type != SignalType.VISUAL_YOLO for signal in segment.detection_signals)
        for segment in segments
    )


def test_composite_detector_transition_recovers_when_score_returns_above_stop_threshold() -> None:
    detector = CompositeDetector(
        visual_detector=None,
        audio_energy_detector=_StubAudioEnergyChannel(
            signals=[
                DetectionSignal(
                    signal_type=SignalType.AUDIO_ENERGY,
                    confidence=0.8,
                    start_time_seconds=0.0,
                    end_time_seconds=5.0,
                    metadata={},
                ),
                DetectionSignal(
                    signal_type=SignalType.AUDIO_ENERGY,
                    confidence=0.6,
                    start_time_seconds=6.0,
                    end_time_seconds=20.0,
                    metadata={},
                ),
            ],
        ),
        audio_classifier=_StubAudioClassifierChannel(
            signals=[
                DetectionSignal(
                    signal_type=SignalType.AUDIO_CLASSIFIER,
                    confidence=0.9,
                    start_time_seconds=0.0,
                    end_time_seconds=5.0,
                    metadata={"label": "music"},
                ),
                DetectionSignal(
                    signal_type=SignalType.AUDIO_CLASSIFIER,
                    confidence=0.9,
                    start_time_seconds=5.0,
                    end_time_seconds=20.0,
                    metadata={"label": "speech"},
                ),
            ],
        ),
        config=DetectionFusionConfig(
            start_threshold=0.55,
            stop_threshold=0.35,
            transition_hold_seconds=2.0,
            min_segment_duration_seconds=5.0,
            visual_weight=0.0,
            audio_energy_weight=0.6,
            audio_classifier_weight=0.4,
        ),
    )

    segments = detector.detect(
        audio_path=Path("audio.wav"),
        video_path=None,
        config=ProjectConfig(enable_yolo_detection=False, min_segment_duration_seconds=5.0),
    )

    assert len(segments) == 1
    assert segments[0].start_time_seconds == pytest.approx(0.0)
    assert segments[0].end_time_seconds == pytest.approx(20.0)
