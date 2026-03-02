"""Domain-level visual activity detection using YOLO inference results."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from cvcutter.domain.models.segment import DetectionSignal
from cvcutter.domain.services.types import Detection, VideoFrame
from cvcutter.shared.types import SignalType

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from cvcutter.domain.services.model_runner import VisualDetectorRunner

_DEFAULT_INSTRUMENT_LABELS = {
    "violin",
    "viola",
    "cello",
    "double_bass",
    "flute",
    "clarinet",
    "saxophone",
    "trumpet",
    "trombone",
    "tuba",
    "guitar",
    "harp",
    "drum",
    "piano",
}


class VisualActivityDetector:
    """Convert YOLO detections into visual activity intervals."""

    def __init__(
        self,
        model_runner: VisualDetectorRunner,
        *,
        frame_sampler: Callable[[Path, float], Iterable[VideoFrame]] | None = None,
        instrument_labels: set[str] | None = None,
        min_detection_confidence: float = 0.25,
    ) -> None:
        if min_detection_confidence < 0 or min_detection_confidence > 1:
            raise ValueError("min_detection_confidence must be between 0 and 1.")
        self._model_runner = model_runner
        self._frame_sampler = frame_sampler or self._default_frame_sampler
        self._instrument_labels = {
            label.strip().lower() for label in (instrument_labels or _DEFAULT_INSTRUMENT_LABELS)
        }
        self._min_detection_confidence = min_detection_confidence

    def detect_activity(self, video_path: Path, fps: float = 1.0) -> list[DetectionSignal]:
        """Detect visual activity intervals based on performers and instruments."""
        if fps <= 0:
            raise ValueError("fps must be greater than zero.")
        samples: list[dict[str, float | bool | int]] = []
        for frame in self._frame_sampler(Path(video_path), fps):
            detections = self._filter_relevant(self._model_runner.detect(frame))
            person_count = sum(1 for detection in detections if detection.class_name.lower() == "person")
            instrument_present = any(
                detection.class_name.lower() in self._instrument_labels for detection in detections
            )
            activity_confidence = max((detection.confidence for detection in detections), default=0.0)
            samples.append(
                {
                    "time_seconds": frame.timestamp_seconds,
                    "person_count": person_count,
                    "instrument_present": instrument_present,
                    "confidence": activity_confidence,
                    "active": person_count > 0 or instrument_present,
                },
            )
        if not samples:
            return []

        return self._samples_to_signals(samples, fps)

    def _filter_relevant(self, detections: list[Detection]) -> list[Detection]:
        return [detection for detection in detections if detection.confidence >= self._min_detection_confidence]

    def _samples_to_signals(self, samples: list[dict[str, float | bool | int]], fps: float) -> list[DetectionSignal]:
        """Aggregate sampled detections into contiguous active intervals."""
        signals: list[DetectionSignal] = []
        run_start: int | None = None
        for index, sample in enumerate(samples):
            is_active = bool(sample["active"])
            if is_active and run_start is None:
                run_start = index
                continue
            if not is_active and run_start is not None:
                signal = self._build_signal(samples, run_start, index - 1, fps)
                if signal is not None:
                    signals.append(signal)
                run_start = None
        if run_start is not None:
            signal = self._build_signal(samples, run_start, len(samples) - 1, fps)
            if signal is not None:
                signals.append(signal)
        return signals

    def _build_signal(
        self,
        samples: list[dict[str, float | bool | int]],
        run_start: int,
        run_end: int,
        fps: float,
    ) -> DetectionSignal | None:
        run = samples[run_start : run_end + 1]
        if not run:
            return None
        step = self._sample_step_seconds(samples, fps)
        start_seconds = float(run[0]["time_seconds"])
        end_seconds = float(run[-1]["time_seconds"]) + step
        confidences = [float(item["confidence"]) for item in run]
        person_counts = [int(item["person_count"]) for item in run]
        instrument_presence = [bool(item["instrument_present"]) for item in run]
        return DetectionSignal(
            signal_type=SignalType.VISUAL_YOLO,
            confidence=float(np.clip(np.mean(confidences), 0.0, 1.0)),
            start_time_seconds=start_seconds,
            end_time_seconds=end_seconds,
            metadata={
                "source": "VisualActivityDetector",
                "model_version": self._model_runner.model_version(),
                "person_count_max": max(person_counts, default=0),
                "instrument_present": any(instrument_presence),
                "time_series": run,
            },
        )

    @staticmethod
    def _sample_step_seconds(samples: list[dict[str, float | bool | int]], fps: float) -> float:
        if len(samples) < 2:
            return 1.0 / fps
        first = float(samples[0]["time_seconds"])
        second = float(samples[1]["time_seconds"])
        return max(second - first, 1e-3)

    @staticmethod
    def _default_frame_sampler(video_path: Path, fps: float) -> Iterable[VideoFrame]:
        """Sample frames from input video at approximately the requested fps."""
        if not video_path.exists():
            raise FileNotFoundError(f"Video file does not exist: {video_path}")

        import cv2

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise ValueError(f"Failed to open video file: {video_path}")

        source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if source_fps <= 0:
            source_fps = fps
        frame_step = max(round(source_fps / fps), 1)

        frame_index = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if frame_index % frame_step == 0:
                    timestamp = frame_index / source_fps
                    yield VideoFrame(
                        data=np.asarray(frame),
                        timestamp_seconds=float(timestamp),
                        frame_index=frame_index,
                    )
                frame_index += 1
        finally:
            capture.release()
