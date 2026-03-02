"""Main processing pipeline orchestration for baseline video-to-export flow."""

from __future__ import annotations

import logging
import threading
from contextlib import suppress
from functools import partial
from time import perf_counter
from typing import TYPE_CHECKING

from cvcutter.application.pipeline_resources import PipelineResourcesMixin
from cvcutter.infrastructure.logging.structured_logger import (
    log_resource_telemetry,
    log_stage_transition,
)
from cvcutter.shared.types import (
    ExportStatus,
    PipelineStage,
    ProcessingState,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from cvcutter.application.checkpoint_manager import CheckpointManager, ResumeDecision
    from cvcutter.domain.detection.audio_energy import AudioEnergyDetector
    from cvcutter.domain.detection.detector import CompositeDetector, DetectionFusionConfig
    from cvcutter.domain.models.project import ConcertProject
    from cvcutter.domain.models.segment import PerformanceSegment
    from cvcutter.domain.services.project_store import ProjectStore
    from cvcutter.domain.services.types import ProgressEvent
    from cvcutter.domain.services.video_io import VideoIOService


if not TYPE_CHECKING:
    try:
        from cvcutter.domain.detection.audio_energy import AudioEnergyDetector
        from cvcutter.domain.detection.detector import CompositeDetector, DetectionFusionConfig
    except ImportError:  # pragma: no cover - temporary fallback until detector module lands.
        AudioEnergyDetector = None  # type: ignore[assignment]
        CompositeDetector = None  # type: ignore[assignment]
        DetectionFusionConfig = None  # type: ignore[assignment]

class _PipelinePausedError(Exception):
    """Internal control-flow exception used when pause is requested."""


class _PipelineCancelledError(Exception):
    """Internal control-flow exception used when cancellation is requested."""


class PipelineOrchestrator(PipelineResourcesMixin):
    """Coordinate pipeline stages using domain services and protocol-typed ports."""

    _active_job_lock = threading.Lock()
    _active_job_project_id: str | None = None

    def __init__(
        self,
        video_io: VideoIOService,
        checkpoint_manager: CheckpointManager,
        project_store: ProjectStore,
        logger: logging.Logger | None = None,
    ) -> None:
        self._video_io = video_io
        self._checkpoint_manager = checkpoint_manager
        self._project_store = project_store
        self._logger = logger or logging.getLogger(__name__)
        self._pause_requested = False
        self._cancel_requested = False
        self._active_config_hash: str | None = None

    def run(
        self,
        project: ConcertProject,
        progress_callback: Callable[[ProgressEvent], None] | None = None,
    ) -> ConcertProject:
        """Execute pipeline stages with automatic checkpoint reuse where valid."""
        return self._run_with_guard(
            project,
            progress_callback=progress_callback,
            run_mode="run",
            resume_decision=None,
        )

    def resume(
        self,
        project: ConcertProject,
        progress_callback: Callable[[ProgressEvent], None] | None = None,
    ) -> ConcertProject:
        """Resume interrupted processing by validating checkpoints before execution."""
        return self._run_with_guard(
            project,
            progress_callback=progress_callback,
            run_mode="resume",
            resume_decision=None,
        )

    def restart(
        self,
        project: ConcertProject,
        progress_callback: Callable[[ProgressEvent], None] | None = None,
    ) -> ConcertProject:
        """Invalidate checkpoints and execute the full pipeline from scratch."""
        return self._run_with_guard(
            project,
            progress_callback=progress_callback,
            run_mode="restart",
            resume_decision=None,
        )

    def _run_with_guard(
        self,
        project: ConcertProject,
        *,
        progress_callback: Callable[[ProgressEvent], None] | None,
        run_mode: str,
        resume_decision: ResumeDecision | None,
    ) -> ConcertProject:
        """Enforce single-active-job execution and dispatch run mode behavior."""
        project_id = self._project_id(project)
        self._acquire_active_job(project_id)
        try:
            resolved_resume_decision = resume_decision
            if run_mode == "restart":
                invalidated_ids = self._checkpoint_manager.invalidate_with_cascade(
                    project_id,
                    PipelineStage.CONCATENATION,
                )
                log_stage_transition(
                    self._logger,
                    "PIPELINE",
                    "RESTART_REQUESTED",
                    decision="restart",
                    decision_reason="user_requested_restart",
                    output_refs=[f"invalidated:{len(invalidated_ids)}"],
                )
            if run_mode == "resume":
                if resolved_resume_decision is None:
                    resolved_resume_decision = self._checkpoint_manager.make_resume_decision(
                        project_id=project_id,
                        current_input_hashes=self._resume_input_hashes(project),
                        current_config=self._resume_config_snapshots(project),
                        current_model_versions=self._resume_model_versions(),
                    )
                decision_reason = self._resume_decision_reason(resolved_resume_decision)
                log_stage_transition(
                    self._logger,
                    "PIPELINE",
                    "RESUME_DECISION",
                    decision="resume" if resolved_resume_decision.can_resume else "restart",
                    decision_reason=decision_reason,
                )
                log_stage_transition(
                    self._logger,
                    "PIPELINE",
                    "RESUME_POINT",
                    decision="resume" if resolved_resume_decision.can_resume else "restart",
                    decision_reason=decision_reason,
                )
            return self._run_pipeline(project, progress_callback)
        finally:
            self._release_active_job(project_id)

    @classmethod
    def _acquire_active_job(cls, project_id: str) -> None:
        """Guard against concurrent pipeline jobs within the current process."""
        with cls._active_job_lock:
            if cls._active_job_project_id is not None:
                raise RuntimeError(
                    f"Another pipeline job is already active for project {cls._active_job_project_id}.",
                )
            cls._active_job_project_id = project_id

    @classmethod
    def _release_active_job(cls, project_id: str) -> None:
        """Release the active-job slot for the completed/failed pipeline run."""
        with cls._active_job_lock:
            if cls._active_job_project_id == project_id:
                cls._active_job_project_id = None

    def _run_pipeline(
        self,
        project: ConcertProject,
        progress_callback: Callable[[ProgressEvent], None] | None = None,
    ) -> ConcertProject:
        """Run baseline stages with checkpoint-aware resume behavior."""
        project_id = self._project_id(project)
        self._active_config_hash = self._config_hash(self._config_snapshot(project))
        concatenated_path: Path | None = None
        segments: list[PerformanceSegment] = []
        sync_offset: float | None = None

        log_stage_transition(
            self._logger,
            "PIPELINE",
            "STARTED",
            input_refs=[str(source.file_path) for source in project.source_videos],
            decision="start",
            decision_reason=f"project_id={project_id}",
        )

        try:
            self._check_control_flags(project, "PIPELINE_START")
            self._apply_config_changes(project, "PIPELINE_START")

            self._transition_state(project, ProcessingState.CONCATENATING)
            concat_hashes = self._hash_source_inputs(project)
            concat_models = self._model_versions(PipelineStage.CONCATENATION)
            concat_checkpoint = self._find_valid_checkpoint(
                project,
                PipelineStage.CONCATENATION,
                concat_hashes,
                concat_models,
            )
            resumed_concat = self._checkpoint_output_path(concat_checkpoint)
            if concat_checkpoint is not None and resumed_concat is not None and resumed_concat.exists():
                concatenated_path = resumed_concat
                self._emit_progress(
                    progress_callback,
                    PipelineStage.CONCATENATION.value,
                    1,
                    1,
                    "Valid concatenation checkpoint found; stage skipped.",
                )
                log_stage_transition(
                    self._logger,
                    PipelineStage.CONCATENATION.value,
                    "SKIPPED",
                    checkpoint_id=str(concat_checkpoint.id),
                    output_refs=[str(concatenated_path)],
                    decision="resume",
                    decision_reason="valid checkpoint",
                )
            else:
                concatenated_path = self._run_concatenation(project, progress_callback)

            self._check_control_flags(project, "AFTER_CONCATENATION")
            self._apply_config_changes(project, "AFTER_CONCATENATION")
            self._transition_state(project, ProcessingState.DETECTING)
            detection_hashes = self._hash_for_concatenated_stage(concatenated_path)
            detection_models = self._model_versions(PipelineStage.DETECTION)
            detection_checkpoint = self._find_valid_checkpoint(
                project,
                PipelineStage.DETECTION,
                detection_hashes,
                detection_models,
            )
            loaded_segments = self._project_store.load_segments(project_id)
            has_explicit_empty = self._checkpoint_declares_zero_segments(detection_checkpoint)
            if detection_checkpoint is not None and (loaded_segments or has_explicit_empty):
                segments = loaded_segments
                self._emit_progress(
                    progress_callback,
                    PipelineStage.DETECTION.value,
                    1,
                    1,
                    "Valid detection checkpoint found; stage skipped.",
                )
                log_stage_transition(
                    self._logger,
                    PipelineStage.DETECTION.value,
                    "SKIPPED",
                    checkpoint_id=str(detection_checkpoint.id),
                    output_refs=[f"segments:{len(segments)}"],
                    decision="resume",
                    decision_reason="valid checkpoint",
                )
            else:
                segments = self._run_detection(project, concatenated_path, progress_callback)

            self._check_control_flags(project, "AFTER_DETECTION")
            self._apply_config_changes(project, "AFTER_DETECTION")
            self._transition_state(project, ProcessingState.SYNCING_AUDIO)
            audio_sync_hashes = self._hash_for_audio_sync_stage(project, concatenated_path)
            audio_sync_models = self._model_versions(PipelineStage.AUDIO_SYNC)
            audio_sync_checkpoint = self._find_valid_checkpoint(
                project,
                PipelineStage.AUDIO_SYNC,
                audio_sync_hashes,
                audio_sync_models,
            )
            if audio_sync_checkpoint is not None:
                sync_offset = self._checkpoint_sync_offset(audio_sync_checkpoint)
                if project.external_audio is not None:
                    project.external_audio.sync_offset_seconds = sync_offset
                    self._project_store.save_project(project)
                self._emit_progress(
                    progress_callback,
                    PipelineStage.AUDIO_SYNC.value,
                    1,
                    1,
                    "Valid audio-sync checkpoint found; stage skipped.",
                )
                log_stage_transition(
                    self._logger,
                    PipelineStage.AUDIO_SYNC.value,
                    "SKIPPED",
                    checkpoint_id=str(audio_sync_checkpoint.id),
                    output_refs=[f"sync_offset:{sync_offset}" if sync_offset is not None else "sync_offset:none"],
                    decision="resume",
                    decision_reason="valid checkpoint",
                )
            else:
                sync_offset = self._run_audio_sync(project, concatenated_path, progress_callback)

            self._check_control_flags(project, "AFTER_AUDIO_SYNC")
            self._apply_config_changes(project, "AFTER_AUDIO_SYNC")
            self._transition_state(project, ProcessingState.READY_FOR_EXPORT)
            self._emit_progress(
                progress_callback,
                ProcessingState.READY_FOR_EXPORT.value,
                1,
                1,
                "Pipeline reached READY_FOR_EXPORT.",
            )

            self._check_control_flags(project, "AFTER_READY_FOR_EXPORT")
            self._apply_config_changes(project, "AFTER_READY_FOR_EXPORT")
            self._transition_state(project, ProcessingState.EXPORTING)
            exported_segments = self._run_export(
                project,
                segments,
                concatenated_path,
                sync_offset,
                progress_callback,
            )
            self._project_store.save_segments(project_id, exported_segments)

            self._transition_state(project, ProcessingState.MAPPING)
            self._emit_progress(
                progress_callback,
                PipelineStage.EXPORT.value,
                len(exported_segments),
                len(exported_segments),
                "Export stage completed.",
            )
            log_stage_transition(
                self._logger,
                "PIPELINE",
                "COMPLETED",
                output_refs=[str(segment.exported_file_path) for segment in exported_segments if segment.exported_file_path],
                decision="success",
                decision_reason=f"project_id={project_id}",
            )
            return project
        except (_PipelinePausedError, _PipelineCancelledError):
            return project
        except Exception as exc:
            self._mark_failed(project, exc)
            raise
        finally:
            self._pause_requested = False
            self._cancel_requested = False
            self._active_config_hash = None

    def _run_concatenation(
        self,
        project: ConcertProject,
        progress_callback: Callable[[ProgressEvent], None] | None,
    ) -> Path:
        """Concatenate ordered source videos into a single intermediate artifact."""
        stage = PipelineStage.CONCATENATION
        source_paths = [video.file_path for video in sorted(project.source_videos, key=lambda item: item.order_index)]
        output_format = project.config_snapshot.output_format.strip(".") or "mp4"
        output_path = project.output_directory / f"{self._project_id(project)}_concatenated.{output_format}"
        project.output_directory.mkdir(parents=True, exist_ok=True)

        log_stage_transition(
            self._logger,
            stage.value,
            "STARTED",
            input_refs=[str(path) for path in source_paths],
            output_refs=[str(output_path)],
        )

        def on_progress(current: int, total: int) -> None:
            self._emit_progress(
                progress_callback,
                stage.value,
                current,
                total,
                "Concatenating source videos.",
            )

        concatenated_path = self._video_io.concatenate(source_paths, output_path, progress_callback=on_progress)
        input_hashes = self._hash_source_inputs(project)
        model_versions = self._model_versions(stage)
        checkpoint = self._save_checkpoint(
            project=project,
            stage=stage,
            input_hashes=input_hashes,
            model_versions=model_versions,
            output_references=[str(concatenated_path)],
        )

        self._emit_progress(progress_callback, stage.value, 1, 1, "Concatenation completed.")
        log_stage_transition(
            self._logger,
            stage.value,
            "COMPLETED",
            checkpoint_id=str(checkpoint.id),
            input_refs=list(input_hashes),
            output_refs=[str(concatenated_path)],
        )
        return concatenated_path

    def _run_detection(
        self,
        project: ConcertProject,
        concatenated_path: Path,
        progress_callback: Callable[[ProgressEvent], None] | None,
    ) -> list[PerformanceSegment]:
        """Detect performance boundaries with multimodal fusion and fallbacks."""
        stage = PipelineStage.DETECTION
        log_stage_transition(
            self._logger,
            stage.value,
            "STARTED",
            input_refs=[str(concatenated_path)],
        )
        self._emit_progress(progress_callback, stage.value, 0, 1, "Detecting provisional segments.")

        if AudioEnergyDetector is None or CompositeDetector is None or DetectionFusionConfig is None:
            raise RuntimeError("Detection modules are unavailable.")

        audio_energy_detector = AudioEnergyDetector()
        audio_classifier = self._build_audio_classifier_channel()
        visual_detector, visual_error = self._build_visual_detector_channel(project)
        fusion_detector = CompositeDetector(
            visual_detector=visual_detector,
            audio_energy_detector=audio_energy_detector,
            audio_classifier=audio_classifier,
            config=DetectionFusionConfig(
                min_segment_duration_seconds=project.config_snapshot.min_segment_duration_seconds,
            ),
        )
        if visual_error is not None and project.config_snapshot.enable_yolo_detection:
            self._emit_progress(
                progress_callback,
                stage.value,
                0,
                1,
                "YOLO unavailable; using audio-only detection (reduced accuracy).",
            )

        segments = fusion_detector.detect(
            audio_path=concatenated_path,
            video_path=concatenated_path,
            config=project.config_snapshot,
        )
        for segment in segments:
            for signal in segment.detection_signals:
                signal.metadata["effective_detection_mode"] = segment.effective_detection_mode
                if segment.fallback_reason is not None:
                    signal.metadata["fallback_reason"] = segment.fallback_reason
                    signal.metadata["accuracy_notice"] = "Reduced accuracy: running without visual channel."

        project_id = self._project_id(project)
        self._project_store.save_segments(project_id, segments)
        input_hashes = self._hash_for_concatenated_stage(concatenated_path)
        model_versions = self._model_versions(stage)
        mode_counts = self._detection_mode_counts(segments)
        output_references = [f"segments:{len(segments)}"] + [
            f"detection_mode:{mode}={count}" for mode, count in sorted(mode_counts.items())
        ]
        checkpoint = self._save_checkpoint(
            project=project,
            stage=stage,
            input_hashes=input_hashes,
            model_versions=model_versions,
            output_references=output_references,
        )

        self._emit_progress(
            progress_callback,
            stage.value,
            len(segments),
            len(segments) if segments else 1,
            f"Detection completed with {len(segments)} segment(s).",
        )
        log_stage_transition(
            self._logger,
            stage.value,
            "COMPLETED",
            checkpoint_id=str(checkpoint.id),
            input_refs=list(input_hashes),
            output_refs=[f"segments:{len(segments)}"],
        )
        return segments

    def _run_audio_sync(
        self,
        project: ConcertProject,
        concatenated_path: Path,
        progress_callback: Callable[[ProgressEvent], None] | None,
    ) -> float | None:
        """Compute external-audio sync offset when external audio is available."""
        stage = PipelineStage.AUDIO_SYNC
        self._emit_progress(progress_callback, stage.value, 0, 1, "Computing audio sync offset.")
        log_stage_transition(
            self._logger,
            stage.value,
            "STARTED",
            input_refs=[str(concatenated_path)],
        )

        offset: float | None = None
        external_audio = project.external_audio
        if external_audio is not None:
            offset = self._invoke_sync_offset(
                concatenated_path=concatenated_path,
                external_audio_path=external_audio.file_path,
                sample_rate=project.config_snapshot.audio_sync_sample_rate,
            )
            external_audio.sync_offset_seconds = offset
        self._project_store.save_project(project)

        input_hashes = self._hash_for_audio_sync_stage(project, concatenated_path)
        model_versions = self._model_versions(stage)
        checkpoint = self._save_checkpoint(
            project=project,
            stage=stage,
            input_hashes=input_hashes,
            model_versions=model_versions,
            output_references=[f"sync_offset:{offset}" if offset is not None else "sync_offset:none"],
        )

        self._emit_progress(progress_callback, stage.value, 1, 1, "Audio sync stage completed.")
        log_stage_transition(
            self._logger,
            stage.value,
            "COMPLETED",
            checkpoint_id=str(checkpoint.id),
            input_refs=list(input_hashes),
            output_refs=[f"sync_offset:{offset}" if offset is not None else "sync_offset:none"],
        )
        return offset

    def _run_export(
        self,
        project: ConcertProject,
        segments: list[PerformanceSegment],
        concatenated_path: Path,
        sync_offset: float | None,
        progress_callback: Callable[[ProgressEvent], None] | None,
    ) -> list[PerformanceSegment]:
        """Export each segment and persist per-segment checkpoints/status transitions."""
        stage = PipelineStage.EXPORT
        log_stage_transition(
            self._logger,
            stage.value,
            "STARTED",
            input_refs=[str(concatenated_path)],
            output_refs=[str(project.output_directory)],
        )
        project.output_directory.mkdir(parents=True, exist_ok=True)

        sorted_segments = sorted(segments, key=lambda item: item.segment_index)
        total_segments = len(sorted_segments)

        if total_segments == 0:
            self._emit_progress(progress_callback, stage.value, 1, 1, "No segments to export.")
            self._cleanup_temporary_artifacts(project, concatenated_path)
            return sorted_segments

        self._validate_export_disk_space(project, concatenated_path)
        export_started_at = perf_counter()
        estimated_total_bytes = self._estimate_export_total_bytes(project, sorted_segments, concatenated_path)
        bytes_processed = 0
        log_resource_telemetry(self._logger, stage.value, path=project.output_directory)

        for processed_index, segment in enumerate(sorted_segments, start=1):
            self._check_control_flags(project, f"EXPORT_SEGMENT_{segment.segment_index}")
            self._apply_config_changes(project, f"EXPORT_SEGMENT_{segment.segment_index}")
            can_use_gpu = project.config_snapshot.enable_gpu and self._safe_gpu_check()
            audio_mix = self._build_audio_mix(project, sync_offset)
            input_hashes = self._hash_for_export_stage(project, concatenated_path, segment)
            model_versions = self._model_versions(stage)
            checkpoint = self._find_valid_checkpoint(
                project,
                stage,
                input_hashes,
                model_versions,
                segment_index=segment.segment_index,
            )
            resumed_output = self._resolve_exported_output(segment, checkpoint)
            if resumed_output is not None and resumed_output.exists():
                segment.exported_file_path = resumed_output
                segment.export_status = ExportStatus.EXPORTED
                bytes_processed += resumed_output.stat().st_size
                self._emit_progress(
                    progress_callback,
                    stage.value,
                    processed_index,
                    total_segments,
                    f"Segment {segment.segment_index + 1} already exported; skipped.",
                )
                log_stage_transition(
                    self._logger,
                    stage.value,
                    "SKIPPED",
                    checkpoint_id=str(checkpoint.id) if checkpoint is not None else None,
                    output_refs=[str(resumed_output)],
                    decision="resume",
                    decision_reason=f"segment_index={segment.segment_index}",
                )
                continue

            segment.export_status = ExportStatus.EXPORTING
            self._project_store.save_segments(self._project_id(project), sorted_segments)
            target_path = self._segment_output_path(project, segment)
            self._emit_progress(
                progress_callback,
                stage.value,
                processed_index - 1,
                total_segments,
                f"Exporting segment {segment.segment_index + 1}/{total_segments}.",
            )
            segment_bytes_before = bytes_processed
            on_segment_progress = partial(
                self._emit_export_progress,
                progress_callback=progress_callback,
                stage=stage.value,
                segment_index=segment.segment_index,
                total_segments=total_segments,
                bytes_before=segment_bytes_before,
                export_started_at=export_started_at,
                estimated_total_bytes=estimated_total_bytes,
            )

            exported_path = self._video_io.export_segment(
                source_path=concatenated_path,
                output_path=target_path,
                start_seconds=segment.start_time_seconds,
                end_seconds=segment.end_time_seconds,
                audio_mix=audio_mix,
                quality=project.config_snapshot.output_quality,
                use_gpu=can_use_gpu,
                progress_callback=on_segment_progress,
            )
            bytes_processed += exported_path.stat().st_size if exported_path.exists() else 0
            segment.exported_file_path = exported_path
            segment.export_status = ExportStatus.EXPORTED
            log_resource_telemetry(self._logger, stage.value, path=project.output_directory)

            saved_checkpoint = self._save_checkpoint(
                project=project,
                stage=stage,
                input_hashes=input_hashes,
                model_versions=model_versions,
                output_references=[str(exported_path)],
                segment_index=segment.segment_index,
            )
            self._project_store.save_segments(self._project_id(project), sorted_segments)
            self._emit_progress(
                progress_callback,
                stage.value,
                processed_index,
                total_segments,
                f"Segment {segment.segment_index + 1}/{total_segments} exported.",
            )
            log_stage_transition(
                self._logger,
                stage.value,
                "COMPLETED_SEGMENT",
                checkpoint_id=str(saved_checkpoint.id),
                input_refs=list(input_hashes),
                output_refs=[str(exported_path)],
                decision="exported",
                decision_reason=f"segment_index={segment.segment_index}",
            )

        self._cleanup_temporary_artifacts(project, concatenated_path)
        log_stage_transition(
            self._logger,
            stage.value,
            "COMPLETED",
            output_refs=[str(segment.exported_file_path) for segment in sorted_segments if segment.exported_file_path],
            decision="success",
            decision_reason=f"segments={total_segments}",
        )
        return sorted_segments

    def pause(self) -> None:
        """Request pause at the next stage boundary."""
        self._pause_requested = True
        self._logger.info("Pipeline pause requested.")

    def cancel(self) -> None:
        """Request cancellation at the next stage boundary."""
        self._cancel_requested = True
        self._logger.info("Pipeline cancellation requested.")

    def _transition_state(self, project: ConcertProject, target: ProcessingState) -> None:
        """Transition processing state and persist project snapshots."""
        before_state = project.processing_state
        if before_state == target:
            self._project_store.save_project(project)
            return
        try:
            project.transition_to(target)
            self._project_store.save_project(project)
            log_stage_transition(
                self._logger,
                "STATE",
                "TRANSITION",
                input_refs=[before_state.value],
                output_refs=[target.value],
            )
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid pipeline state transition: {before_state.value} -> {target.value}",
            ) from exc

    def _check_control_flags(self, project: ConcertProject, marker: str) -> None:
        """Apply pause/cancel control flags at deterministic boundaries."""
        if self._cancel_requested:
            self._mark_failed(project, RuntimeError("Pipeline cancelled by user request."), marker)
            raise _PipelineCancelledError
        if self._pause_requested:
            self._transition_state(project, ProcessingState.PAUSED)
            self._emit_progress(
                None,
                "PIPELINE",
                0,
                1,
                f"Paused at {marker}.",
            )
            log_stage_transition(
                self._logger,
                "PIPELINE",
                "PAUSED",
                decision="pause",
                decision_reason=marker,
            )
            raise _PipelinePausedError

    def _mark_failed(
        self,
        project: ConcertProject,
        exc: Exception,
        marker: str = "PIPELINE",
    ) -> None:
        """Transition project to FAILED and emit structured failure logging."""
        with suppress(ValueError):
            project.transition_to(ProcessingState.FAILED)
        self._project_store.save_project(project)
        log_stage_transition(
            self._logger,
            marker,
            "FAILED",
            decision="failure",
            decision_reason=str(exc),
        )
        self._logger.exception("Pipeline failed at %s: %s", marker, exc)

