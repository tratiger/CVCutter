"""Multimodal performance detector combining visual and audio channels."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

import numpy as np

from cvcutter.domain.models.segment import DetectionSignal, PerformanceSegment
from cvcutter.shared.types import SignalType

if TYPE_CHECKING:
    from cvcutter.domain.models.project import ProjectConfig

_STATE_IDLE = "IDLE"
_STATE_PERFORMING = "PERFORMING"
_STATE_TRANSITION = "TRANSITION"


class _AudioEnergyChannel(Protocol):
    def detect_boundaries_with_signals(
        self,
        audio_path: Path,
        sample_rate: int = 22050,
        min_duration: float = 30.0,
    ) -> list[DetectionSignal]:
        ...


class _AudioClassifierChannel(Protocol):
    def classify_segments(
        self,
        audio_path: Path,
        sample_rate: int = 22050,
        window_seconds: float = 1.0,
    ) -> list[DetectionSignal]:
        ...


class _VisualChannel(Protocol):
    def detect_activity(self, video_path: Path, fps: float = 1.0) -> list[DetectionSignal]:
        ...


@dataclass(frozen=True)
class DetectionFusionConfig:
    """Tunable parameters for multimodal signal fusion."""

    start_threshold: float = 0.55
    stop_threshold: float = 0.35
    transition_hold_seconds: float = 4.0
    merge_gap_seconds: float = 1.5
    min_segment_duration_seconds: float = 30.0
    visual_weight: float = 0.3
    audio_energy_weight: float = 0.4
    audio_classifier_weight: float = 0.3

    def __post_init__(self) -> None:
        if not 0.0 <= self.start_threshold <= 1.0:
            raise ValueError("start_threshold must be between 0 and 1.")
        if not 0.0 <= self.stop_threshold <= 1.0:
            raise ValueError("stop_threshold must be between 0 and 1.")
        if self.stop_threshold > self.start_threshold:
            raise ValueError("stop_threshold must be <= start_threshold.")
        if self.transition_hold_seconds < 0:
            raise ValueError("transition_hold_seconds must be >= 0.")
        if self.merge_gap_seconds < 0:
            raise ValueError("merge_gap_seconds must be >= 0.")
        if self.min_segment_duration_seconds <= 0:
            raise ValueError("min_segment_duration_seconds must be > 0.")
        if self.visual_weight < 0 or self.audio_energy_weight < 0 or self.audio_classifier_weight < 0:
            raise ValueError("fusion weights must be >= 0.")

    def for_project(self, project_config: ProjectConfig) -> DetectionFusionConfig:
        return replace(
            self,
            min_segment_duration_seconds=max(
                self.min_segment_duration_seconds,
                project_config.min_segment_duration_seconds,
            ),
        )


@dataclass(frozen=True)
class _FusionInterval:
    start_seconds: float
    end_seconds: float
    score: float


class CompositeDetector:
    """Fuse visual YOLO, audio-energy, and audio-classifier channels into segments."""

    def __init__(
        self,
        *,
        visual_detector: _VisualChannel | None,
        audio_energy_detector: _AudioEnergyChannel,
        audio_classifier: _AudioClassifierChannel | None,
        config: DetectionFusionConfig | None = None,
    ) -> None:
        self._visual_detector = visual_detector
        self._audio_energy_detector = audio_energy_detector
        self._audio_classifier = audio_classifier
        self._config = config or DetectionFusionConfig()

    def detect(
        self,
        audio_path: Path,
        video_path: Path | None,
        config: ProjectConfig,
    ) -> list[PerformanceSegment]:
        """Detect performance segments using weighted multimodal fusion."""
        fusion_config = self._config.for_project(config)
        energy_signals = self._detect_audio_energy(audio_path, fusion_config)
        classifier_signals = self._detect_audio_classifier(audio_path)
        use_classifier = bool(classifier_signals)

        fallback_reason: str | None = None
        visual_signals: list[DetectionSignal] = []
        visual_enabled = config.enable_yolo_detection and video_path is not None
        if not config.enable_yolo_detection:
            fallback_reason = "YOLO_DISABLED"
        elif video_path is None:
            fallback_reason = "VIDEO_UNAVAILABLE"
        elif self._visual_detector is None:
            fallback_reason = "YOLO_UNAVAILABLE"
        else:
            try:
                visual_signals = list(self._visual_detector.detect_activity(Path(video_path)))
            except Exception:
                visual_signals = []
                fallback_reason = "YOLO_UNAVAILABLE"

        use_visual = visual_enabled and fallback_reason is None
        signals_for_fusion = list(energy_signals) + list(classifier_signals)
        if use_visual:
            signals_for_fusion.extend(visual_signals)
        if not signals_for_fusion:
            return []

        intervals = self._build_fusion_intervals(
            signals=signals_for_fusion,
            use_visual=use_visual,
            use_classifier=use_classifier,
            config=fusion_config,
        )
        candidate_ranges = self._run_state_machine(intervals, fusion_config)
        merged_ranges = self._merge_ranges(candidate_ranges, fusion_config.merge_gap_seconds)
        minimum_duration = fusion_config.min_segment_duration_seconds
        bounded_ranges = [
            (start, end) for start, end in merged_ranges if end - start >= minimum_duration
        ]

        mode = "full" if use_visual else "audio_only"
        effective_reason = None if mode == "full" else (fallback_reason or "YOLO_UNAVAILABLE")
        segments: list[PerformanceSegment] = []
        for segment_index, (start_seconds, end_seconds) in enumerate(bounded_ranges):
            segment_signals = self._segment_signals(signals_for_fusion, start_seconds, end_seconds, mode)
            confidence = self._segment_confidence(intervals, start_seconds, end_seconds)
            segments.append(
                PerformanceSegment(
                    id=uuid4(),
                    segment_index=segment_index,
                    start_time_seconds=start_seconds,
                    end_time_seconds=end_seconds,
                    detection_confidence=confidence,
                    effective_detection_mode=mode,
                    detection_signals=segment_signals,
                    fallback_reason=effective_reason,
                ),
            )
        return segments

    def _detect_audio_energy(
        self,
        audio_path: Path,
        config: DetectionFusionConfig,
    ) -> list[DetectionSignal]:
        return list(
            self._audio_energy_detector.detect_boundaries_with_signals(
                audio_path=audio_path,
                min_duration=config.min_segment_duration_seconds,
            ),
        )

    def _detect_audio_classifier(self, audio_path: Path) -> list[DetectionSignal]:
        if self._audio_classifier is None:
            return []
        return list(self._audio_classifier.classify_segments(audio_path=audio_path))

    def _build_fusion_intervals(
        self,
        *,
        signals: list[DetectionSignal],
        use_visual: bool,
        use_classifier: bool,
        config: DetectionFusionConfig,
    ) -> list[_FusionInterval]:
        times = sorted(
            {
                float(signal.start_time_seconds)
                for signal in signals
            }
            | {float(signal.end_time_seconds) for signal in signals},
        )
        if len(times) < 2:
            return []

        intervals: list[_FusionInterval] = []
        for start_seconds, end_seconds in pairwise(times):
            if end_seconds <= start_seconds:
                continue
            midpoint = (start_seconds + end_seconds) / 2.0
            energy_score = self._channel_score(signals, midpoint, SignalType.AUDIO_ENERGY)
            classifier_score = self._classifier_score(signals, midpoint) if use_classifier else 0.0
            visual_score = self._channel_score(signals, midpoint, SignalType.VISUAL_YOLO) if use_visual else 0.0

            weighted_sum = (
                energy_score * config.audio_energy_weight
                + classifier_score * (config.audio_classifier_weight if use_classifier else 0.0)
                + visual_score * (config.visual_weight if use_visual else 0.0)
            )
            denominator = config.audio_energy_weight
            if use_classifier:
                denominator += config.audio_classifier_weight
            if use_visual:
                denominator += config.visual_weight
            if denominator <= 0:
                continue
            score = float(np.clip(weighted_sum / denominator, 0.0, 1.0))
            intervals.append(
                _FusionInterval(
                    start_seconds=float(start_seconds),
                    end_seconds=float(end_seconds),
                    score=score,
                ),
            )
        return intervals

    def _run_state_machine(
        self,
        intervals: list[_FusionInterval],
        config: DetectionFusionConfig,
    ) -> list[tuple[float, float]]:
        if not intervals:
            return []

        state = _STATE_IDLE
        segment_start: float | None = None
        transition_start: float | None = None
        ranges: list[tuple[float, float]] = []

        for interval in intervals:
            score = interval.score
            if state == _STATE_IDLE:
                if score >= config.start_threshold:
                    state = _STATE_PERFORMING
                    segment_start = interval.start_seconds
                continue

            if state == _STATE_PERFORMING:
                if score < config.stop_threshold:
                    state = _STATE_TRANSITION
                    transition_start = interval.start_seconds
                    if interval.end_seconds - transition_start >= config.transition_hold_seconds:
                        if segment_start is not None and transition_start > segment_start:
                            ranges.append((segment_start, transition_start))
                        state = _STATE_IDLE
                        segment_start = None
                        transition_start = None
                continue

            if score >= config.stop_threshold:
                state = _STATE_PERFORMING
                transition_start = None
                continue

            if transition_start is not None and (
                interval.end_seconds - transition_start >= config.transition_hold_seconds
            ):
                if segment_start is not None and transition_start > segment_start:
                    ranges.append((segment_start, transition_start))
                state = _STATE_IDLE
                segment_start = None
                transition_start = None

        if state in {_STATE_PERFORMING, _STATE_TRANSITION} and segment_start is not None:
            segment_end = intervals[-1].end_seconds
            if (
                state == _STATE_TRANSITION
                and transition_start is not None
                and segment_end - transition_start >= config.transition_hold_seconds
            ):
                segment_end = transition_start
            if segment_end > segment_start:
                ranges.append((segment_start, segment_end))
        return ranges

    @staticmethod
    def _merge_ranges(
        ranges: list[tuple[float, float]],
        merge_gap_seconds: float,
    ) -> list[tuple[float, float]]:
        if not ranges:
            return []
        merged: list[tuple[float, float]] = []
        for start_seconds, end_seconds in sorted(ranges, key=lambda item: item[0]):
            if not merged:
                merged.append((start_seconds, end_seconds))
                continue
            previous_start, previous_end = merged[-1]
            if start_seconds - previous_end <= merge_gap_seconds:
                merged[-1] = (previous_start, max(previous_end, end_seconds))
                continue
            merged.append((start_seconds, end_seconds))
        return merged

    @staticmethod
    def _channel_score(signals: list[DetectionSignal], time_seconds: float, signal_type: SignalType) -> float:
        return max(
            (
                signal.confidence
                for signal in signals
                if signal.signal_type == signal_type
                and signal.start_time_seconds <= time_seconds < signal.end_time_seconds
            ),
            default=0.0,
        )

    def _classifier_score(self, signals: list[DetectionSignal], time_seconds: float) -> float:
        active_scores: list[float] = []
        for signal in signals:
            if signal.signal_type != SignalType.AUDIO_CLASSIFIER:
                continue
            if not signal.start_time_seconds <= time_seconds < signal.end_time_seconds:
                continue
            label = str(signal.metadata.get("label", "")).lower()
            factor = self._classifier_activity_factor(label)
            active_scores.append(signal.confidence * factor)
        return max(active_scores, default=0.0)

    @staticmethod
    def _classifier_activity_factor(label: str) -> float:
        if label == "music":
            return 1.0
        if label == "applause":
            return 0.35
        if label == "speech":
            return 0.45
        if label == "silence":
            return 0.0
        return 0.2

    def _segment_confidence(
        self,
        intervals: list[_FusionInterval],
        segment_start: float,
        segment_end: float,
    ) -> float:
        weighted = 0.0
        duration = 0.0
        for interval in intervals:
            overlap_start = max(interval.start_seconds, segment_start)
            overlap_end = min(interval.end_seconds, segment_end)
            if overlap_end <= overlap_start:
                continue
            overlap_duration = overlap_end - overlap_start
            weighted += interval.score * overlap_duration
            duration += overlap_duration
        if duration <= 0:
            return 0.0
        return float(np.clip(weighted / duration, 0.0, 1.0))

    @staticmethod
    def _segment_signals(
        signals: list[DetectionSignal],
        segment_start: float,
        segment_end: float,
        mode: str,
    ) -> list[DetectionSignal]:
        clipped_signals: list[DetectionSignal] = []
        for signal in signals:
            overlap_start = max(signal.start_time_seconds, segment_start)
            overlap_end = min(signal.end_time_seconds, segment_end)
            if overlap_end <= overlap_start:
                continue
            metadata = dict(signal.metadata)
            metadata["effective_detection_mode"] = mode
            clipped_signals.append(
                DetectionSignal(
                    signal_type=signal.signal_type,
                    confidence=signal.confidence,
                    start_time_seconds=overlap_start,
                    end_time_seconds=overlap_end,
                    metadata=metadata,
                ),
            )
        return clipped_signals
