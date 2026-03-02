"""Preview and mapping screen view-model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from cvcutter.domain.models.segment import PerformanceSegment


class PreviewWorkflow(Protocol):
    """Application service contract for preview/mapping workflow actions."""

    def export_segments(self, project_id: str, segments: list[PerformanceSegment]) -> None:
        """Export segments using current manual adjustments."""
        ...

    def auto_map(self, project_id: str) -> None:
        """Run automatic metadata mapping."""
        ...

    def finalize_mappings(self, project_id: str) -> None:
        """Finalize mappings prior to upload."""
        ...


@dataclass
class PreviewViewModel:
    """State and commands for segment preview and metadata mapping."""

    workflow: PreviewWorkflow
    project_id: str
    segments: list[PerformanceSegment] = field(default_factory=list)
    mappings: dict[str, dict[str, Any]] = field(default_factory=dict)
    selected_segment_id: str | None = None
    detection_mode: str = "full"
    reduced_accuracy_notice: str | None = None

    def __post_init__(self) -> None:
        """Initialize mapping slots and FR-012 notice state."""
        for segment in self.segments:
            self._ensure_mapping(str(segment.id))
        self.refresh_notice_from_segments()

    def select_segment(self, segment_id: str) -> None:
        """Select a segment for detail preview and editing."""
        self._find_segment(segment_id)
        self.selected_segment_id = segment_id

    def adjust_boundary(self, segment_id: str, start: float, end: float) -> None:
        """Apply manual boundary adjustments."""
        segment = self._find_segment(segment_id)
        segment.adjust_boundary(start, end)

    def split_segment(self, segment_id: str, split_time: float) -> tuple[PerformanceSegment, PerformanceSegment]:
        """Split one segment into two new segments."""
        segment = self._find_segment(segment_id)
        left, right = segment.split_segment(split_time)
        index = self.segments.index(segment)
        self.segments[index : index + 1] = [left, right]
        for order, current in enumerate(self.segments):
            current.segment_index = order
        self.mappings.pop(segment_id, None)
        self._ensure_mapping(str(left.id))
        self._ensure_mapping(str(right.id))
        self.selected_segment_id = str(left.id)
        self.refresh_notice_from_segments()
        return left, right

    def assign_mapping(self, segment_id: str, program_entry_id: str) -> None:
        """Assign a program entry mapping to a segment."""
        self._find_segment(segment_id)
        self._ensure_mapping(segment_id)["program_entry_id"] = program_entry_id

    def assign_form_response(self, segment_id: str, form_response_id: str) -> None:
        """Assign a form-response mapping to a segment."""
        self._find_segment(segment_id)
        self._ensure_mapping(segment_id)["form_response_id"] = form_response_id

    def clear_mapping(self, segment_id: str) -> None:
        """Clear all mapping fields for a segment."""
        self._find_segment(segment_id)
        mapping = self._ensure_mapping(segment_id)
        mapping["program_entry_id"] = None
        mapping["form_response_id"] = None
        mapping["user_verified"] = False

    def verify_mapping(self, segment_id: str) -> None:
        """Mark the mapping for a segment as user-verified."""
        self._find_segment(segment_id)
        self._ensure_mapping(segment_id)["user_verified"] = True

    def auto_map(self) -> None:
        """Trigger automatic mapping workflow."""
        self.workflow.auto_map(self.project_id)

    def finalize_mappings(self) -> None:
        """Trigger mapping finalization workflow."""
        self.workflow.finalize_mappings(self.project_id)

    def export_segments(self) -> None:
        """Export all currently previewed segments."""
        self.workflow.export_segments(self.project_id, self.segments)

    def refresh_notice_from_segments(self) -> None:
        """Recompute FR-012 reduced-accuracy notice from segment provenance."""
        audio_only = next(
            (segment for segment in self.segments if segment.effective_detection_mode == "audio_only"),
            None,
        )
        if audio_only is None:
            self.detection_mode = "full"
            self.reduced_accuracy_notice = None
            return
        self.detection_mode = "audio_only"
        self.reduced_accuracy_notice = _audio_only_notice(audio_only.fallback_reason)

    def replace_segments(self, segments: list[PerformanceSegment]) -> None:
        """Replace segments while preserving existing mapping assignments where possible."""
        preserved = dict(self.mappings)
        self.segments = list(segments)
        self.mappings = {}
        for segment in self.segments:
            segment_id = str(segment.id)
            self.mappings[segment_id] = preserved.get(
                segment_id,
                {
                    "program_entry_id": None,
                    "form_response_id": None,
                    "user_verified": False,
                },
            )
        if self.selected_segment_id not in self.mappings:
            self.selected_segment_id = next(iter(self.mappings), None)
        self.refresh_notice_from_segments()

    def _find_segment(self, segment_id: str) -> PerformanceSegment:
        """Find a segment by identifier or raise ValueError."""
        for segment in self.segments:
            if str(segment.id) == segment_id:
                return segment
        raise ValueError("指定されたセグメントが見つかりません。")

    def _ensure_mapping(self, segment_id: str) -> dict[str, Any]:
        """Ensure mapping slot exists for a segment."""
        if segment_id not in self.mappings:
            self.mappings[segment_id] = {
                "program_entry_id": None,
                "form_response_id": None,
                "user_verified": False,
            }
        return self.mappings[segment_id]


def _audio_only_notice(fallback_reason: str | None) -> str:
    """Return reason-aware FR-012 reduced-accuracy notice text."""
    normalized = (fallback_reason or "").upper()
    if normalized in {"TOGGLE_DISABLED", "YOLO_DISABLED"}:
        return "YOLO検出が無効化されているため音声のみ検出です。境界精度が低下する可能性があります。"
    if normalized in {"RUNTIME_UNAVAILABLE", "YOLO_UNAVAILABLE", "YOLO_RUNTIME_UNAVAILABLE"}:
        return "YOLO検出が利用できないため音声のみ検出へ切り替えました。境界精度が低下する可能性があります。"
    return "音声のみ検出結果を表示中です。境界精度が低下する可能性があります。"
