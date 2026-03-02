"""Process screen view-model."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from cvcutter.domain.models.segment import PerformanceSegment
    from cvcutter.domain.services.types import ProgressEvent

_STAGE_SEQUENCE = [
    "CONCATENATION",
    "DETECTION",
    "AUDIO_SYNC",
    "EXPORT",
    "MAPPING",
    "UPLOAD",
]
_STAGE_LABELS = {
    "CONCATENATION": "連結",
    "DETECTION": "検出",
    "AUDIO_SYNC": "音声同期",
    "EXPORT": "書き出し",
    "MAPPING": "紐付け",
    "UPLOAD": "アップロード",
}


class ProcessingError(Exception):
    """Domain/application processing failure."""


class UploadError(Exception):
    """Domain/application upload failure."""


class ConfigurationError(Exception):
    """Domain/application configuration failure."""


class ProcessingWorkflow(Protocol):
    """Application service contract for long-running processing operations."""

    def start(
        self,
        project_id: str,
        progress_callback,
    ) -> list[PerformanceSegment]:
        """Start processing from scratch."""
        ...

    def resume(
        self,
        project_id: str,
        progress_callback,
    ) -> list[PerformanceSegment]:
        """Resume processing from existing checkpoints."""
        ...

    def pause(self) -> None:
        """Request pause at the next safe boundary."""
        ...

    def cancel(self) -> None:
        """Request cancellation at the next safe boundary."""
        ...


@dataclass(frozen=True)
class SegmentSummary:
    """Presentation DTO for process-screen segment summaries."""

    segment_id: str
    segment_index: int
    start_time_seconds: float
    end_time_seconds: float
    effective_detection_mode: str
    fallback_reason: str | None
    detection_confidence: float


@dataclass
class ProcessViewModel:
    """State and commands for processing workflow execution."""

    workflow: ProcessingWorkflow
    project_id: str = "active-project"
    current_stage: str = "待機"
    stage_progress: float = 0.0
    overall_progress: float = 0.0
    estimated_time_remaining: str = "-"
    current_operation: str = "処理待機中"
    detected_segments: list[SegmentSummary] = field(default_factory=list)
    is_processing: bool = False
    is_resumable: bool = False
    errors: list[str] = field(default_factory=list)
    gpu_enabled: bool = False
    detection_mode: str = "full"
    reduced_accuracy_notice: str | None = None
    _pause_requested: bool = False
    _cancel_requested: bool = False
    _run_lock: Lock = field(default_factory=Lock, repr=False)

    def start_processing(self, project_id: str | None = None) -> None:
        """Start processing from scratch."""
        active_project_id = project_id or self.project_id
        self._run(project_id=active_project_id, use_resume=False)

    def resume_processing(self, project_id: str | None = None) -> None:
        """Resume processing from checkpoints."""
        active_project_id = project_id or self.project_id
        self._run(project_id=active_project_id, use_resume=True)

    def pause_processing(self) -> None:
        """Pause the running processing task."""
        self._pause_requested = True
        try:
            self.workflow.pause()
        except Exception as exc:
            self._pause_requested = False
            self.errors.append(f"一時停止に失敗しました: {exc}")
            self.current_operation = "一時停止に失敗しました。"
            return
        self.current_operation = "一時停止を要求しました。"

    def cancel_processing(self) -> None:
        """Cancel the running processing task."""
        self._cancel_requested = True
        try:
            self.workflow.cancel()
        except Exception as exc:
            self._cancel_requested = False
            self.errors.append(f"キャンセルに失敗しました: {exc}")
            self.current_operation = "キャンセルに失敗しました。"
            return
        self.current_operation = "キャンセルしました。"

    def start(self, project_id: str | None = None) -> None:
        """Alias command for start_processing()."""
        self.start_processing(project_id)

    def resume(self, project_id: str | None = None) -> None:
        """Alias command for resume_processing()."""
        self.resume_processing(project_id)

    def pause(self) -> None:
        """Alias command for pause_processing()."""
        self.pause_processing()

    def cancel(self) -> None:
        """Alias command for cancel_processing()."""
        self.cancel_processing()

    def on_progress(self, event: ProgressEvent) -> None:
        """Apply one progress callback event to view-model state."""
        if self._pause_requested or self._cancel_requested:
            return
        self.current_stage = _STAGE_LABELS.get(event.stage.upper(), event.stage)
        self.stage_progress = (
            0.0
            if event.total <= 0
            else max(0.0, min(1.0, float(event.current) / float(event.total)))
        )
        self.overall_progress = self._overall_progress(event.stage, self.stage_progress)
        self.current_operation = event.message
        lowered = event.message.lower()
        if "audio_only" in lowered or "audio-only" in lowered:
            self._set_audio_only_notice(None)

    @staticmethod
    def translate_error(exc: Exception) -> str:
        """Translate typed domain/application errors to Japanese UI messages."""
        if isinstance(exc, ProcessingError):
            return "動画処理中に問題が発生しました。入力ファイルと設定を確認してください。"
        if isinstance(exc, UploadError):
            return "アップロード処理で問題が発生しました。ネットワークと認証状態を確認してください。"
        if isinstance(exc, ConfigurationError):
            return "設定の読み込みまたは保存に失敗しました。設定内容を確認してください。"
        return "予期しないエラーが発生しました。ログを確認してください。"

    def _run(self, *, project_id: str, use_resume: bool) -> None:
        """Run start/resume workflow with consistent state management."""
        if not self._run_lock.acquire(blocking=False):
            return
        try:
            self.is_processing = True
            self.project_id = project_id
            self._pause_requested = False
            self._cancel_requested = False
            self.errors.clear()
            self.detected_segments.clear()
            self.current_operation = "処理を開始しています..."
            self.detection_mode = "full"
            self.reduced_accuracy_notice = None
            segments = (
                self.workflow.resume(project_id, self.on_progress)
                if use_resume
                else self.workflow.start(project_id, self.on_progress)
            )
            self._apply_segments(segments)
            if self._cancel_requested:
                self.current_operation = "キャンセルしました。"
            elif self._pause_requested:
                self.current_operation = "一時停止を要求しました。"
            else:
                self.current_operation = "処理が完了しました。"
        except Exception as exc:
            self.detection_mode = "full"
            self.reduced_accuracy_notice = None
            self.errors.append(self.translate_error(exc))
            self.current_operation = "処理に失敗しました。"
        finally:
            self.is_processing = False
            self._run_lock.release()

    def _apply_segments(self, segments: list[PerformanceSegment]) -> None:
        """Update segment summaries and FR-012 detection mode notice state."""
        self.detected_segments = [
            SegmentSummary(
                segment_id=str(segment.id),
                segment_index=segment.segment_index,
                start_time_seconds=segment.start_time_seconds,
                end_time_seconds=segment.end_time_seconds,
                effective_detection_mode=segment.effective_detection_mode,
                fallback_reason=segment.fallback_reason,
                detection_confidence=segment.detection_confidence,
            )
            for segment in segments
        ]
        audio_only = next(
            (segment for segment in segments if segment.effective_detection_mode == "audio_only"),
            None,
        )
        if audio_only is None:
            self.detection_mode = "full"
            self.reduced_accuracy_notice = None
            return
        self._set_audio_only_notice(audio_only.fallback_reason)

    def _set_audio_only_notice(self, fallback_reason: str | None) -> None:
        """Set reduced-accuracy notice per FR-012 audio-only fallback reasons."""
        self.detection_mode = "audio_only"
        normalized = (fallback_reason or "").upper()
        if normalized in {"TOGGLE_DISABLED", "YOLO_DISABLED"}:
            self.reduced_accuracy_notice = (
                "YOLO検出が設定で無効化されているため音声のみ検出です。境界精度が低下する可能性があります。"
            )
            return
        if normalized in {"RUNTIME_UNAVAILABLE", "YOLO_UNAVAILABLE", "YOLO_RUNTIME_UNAVAILABLE"}:
            self.reduced_accuracy_notice = (
                "YOLO検出が利用できないため音声のみ検出へ切り替えました。境界精度が低下する可能性があります。"
            )
            return
        self.reduced_accuracy_notice = "音声のみ検出モードのため境界精度が低下する可能性があります。"

    def _overall_progress(self, stage: str, stage_progress: float) -> float:
        """Approximate overall progress from stage position and stage ratio."""
        upper = stage.upper()
        if upper not in _STAGE_SEQUENCE:
            return stage_progress
        index = _STAGE_SEQUENCE.index(upper)
        return min(1.0, max(0.0, (index + stage_progress) / len(_STAGE_SEQUENCE)))
