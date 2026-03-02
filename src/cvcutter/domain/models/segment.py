"""Segment-related domain entities used by detection and export workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from cvcutter.shared.types import ExportStatus, SignalType

if TYPE_CHECKING:
    from pathlib import Path

_DETECTION_MODES = {"full", "audio_only"}


def _validate_time_range(start_time_seconds: float, end_time_seconds: float) -> None:
    """Validate an inclusive-exclusive time range."""
    if start_time_seconds < 0:
        raise ValueError("start_time_seconds must be >= 0.")
    if end_time_seconds <= start_time_seconds:
        raise ValueError("end_time_seconds must be greater than start_time_seconds.")


def _clip_signal_to_range(
    signal: DetectionSignal,
    range_start: float,
    range_end: float,
) -> DetectionSignal | None:
    """Clip a detection signal to a target range, returning None when disjoint."""
    overlap_start = max(signal.start_time_seconds, range_start)
    overlap_end = min(signal.end_time_seconds, range_end)
    if overlap_end <= overlap_start:
        return None

    return DetectionSignal(
        signal_type=signal.signal_type,
        confidence=signal.confidence,
        start_time_seconds=overlap_start,
        end_time_seconds=overlap_end,
        metadata=dict(signal.metadata),
    )


@dataclass(frozen=True)
class DetectionSignal:
    """Value object representing one detection-channel contribution."""

    signal_type: SignalType
    confidence: float
    start_time_seconds: float
    end_time_seconds: float
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate detection-signal bounds."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0.")
        _validate_time_range(self.start_time_seconds, self.end_time_seconds)


@dataclass
class PerformanceSegment:
    """Detected timeline segment representing a performance window."""

    id: UUID
    segment_index: int
    start_time_seconds: float
    end_time_seconds: float
    detection_confidence: float
    effective_detection_mode: str
    detection_signals: list[DetectionSignal]
    fallback_reason: str | None = None
    exported_file_path: Path | None = None
    export_status: ExportStatus = ExportStatus.NOT_EXPORTED
    user_adjusted: bool = False

    def __post_init__(self) -> None:
        """Validate segment invariants."""
        if isinstance(self.id, str):
            self.id = UUID(self.id)

        if self.segment_index < 0:
            raise ValueError("segment_index must be >= 0.")
        _validate_time_range(self.start_time_seconds, self.end_time_seconds)
        if not 0.0 <= self.detection_confidence <= 1.0:
            raise ValueError("detection_confidence must be between 0.0 and 1.0.")
        if self.effective_detection_mode not in _DETECTION_MODES:
            raise ValueError("effective_detection_mode must be either 'full' or 'audio_only'.")

        if self.effective_detection_mode == "audio_only" and not self.fallback_reason:
            raise ValueError("fallback_reason is required when effective_detection_mode is 'audio_only'.")
        if self.effective_detection_mode == "full" and self.fallback_reason is not None:
            raise ValueError("fallback_reason must be None when effective_detection_mode is 'full'.")

    def adjust_boundary(self, new_start: float, new_end: float) -> None:
        """Manually adjust this segment boundary and mark as user-adjusted."""
        _validate_time_range(new_start, new_end)
        self.start_time_seconds = new_start
        self.end_time_seconds = new_end
        self.user_adjusted = True

    def split_segment(self, split_time: float) -> tuple[PerformanceSegment, PerformanceSegment]:
        """Split this segment into two user-adjusted segments at split_time."""
        if not self.start_time_seconds < split_time < self.end_time_seconds:
            raise ValueError("split_time must be strictly between segment boundaries.")

        left_signals: list[DetectionSignal] = []
        right_signals: list[DetectionSignal] = []
        for signal in self.detection_signals:
            left_signal = _clip_signal_to_range(signal, self.start_time_seconds, split_time)
            if left_signal is not None:
                left_signals.append(left_signal)

            right_signal = _clip_signal_to_range(signal, split_time, self.end_time_seconds)
            if right_signal is not None:
                right_signals.append(right_signal)

        left_segment = PerformanceSegment(
            id=uuid4(),
            segment_index=self.segment_index,
            start_time_seconds=self.start_time_seconds,
            end_time_seconds=split_time,
            detection_confidence=self.detection_confidence,
            effective_detection_mode=self.effective_detection_mode,
            detection_signals=left_signals,
            fallback_reason=self.fallback_reason,
            exported_file_path=None,
            export_status=ExportStatus.NOT_EXPORTED,
            user_adjusted=True,
        )
        right_segment = PerformanceSegment(
            id=uuid4(),
            segment_index=self.segment_index + 1,
            start_time_seconds=split_time,
            end_time_seconds=self.end_time_seconds,
            detection_confidence=self.detection_confidence,
            effective_detection_mode=self.effective_detection_mode,
            detection_signals=right_signals,
            fallback_reason=self.fallback_reason,
            exported_file_path=None,
            export_status=ExportStatus.NOT_EXPORTED,
            user_adjusted=True,
        )
        return left_segment, right_segment
