"""Pipeline helper mixin for resource/utility logic used by PipelineOrchestrator."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.domain.services.types import AudioMixConfig, DiskSpaceInfo, ProgressEvent
from cvcutter.infrastructure.logging.structured_logger import log_stage_transition
from cvcutter.shared.hashing import compute_file_hash
from cvcutter.shared.types import CheckpointStatus, PipelineStage

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from cvcutter.application.checkpoint_manager import CheckpointManager, ResumeDecision
    from cvcutter.domain.detection.audio_classifier import AudioContentClassifier
    from cvcutter.domain.detection.audio_energy import AudioEnergyDetector
    from cvcutter.domain.detection.visual_detector import VisualActivityDetector
    from cvcutter.domain.models.project import ConcertProject
    from cvcutter.domain.models.segment import PerformanceSegment
    from cvcutter.domain.services.project_store import ProjectStore
    from cvcutter.domain.services.video_io import VideoIOService
    from cvcutter.infrastructure.models.audio_classifier_runner import OnnxAudioClassifierRunner
    from cvcutter.infrastructure.models.yolo_runner import YoloModelRunner

try:
    from cvcutter.domain.audio.sync import compute_sync_offset
except ImportError:  # pragma: no cover - temporary fallback until sync module lands.
    def compute_sync_offset(*args: Any, **kwargs: Any) -> float | dict[str, Any] | None:
        """Fallback sync-offset stub when the domain sync module is unavailable."""
        del args, kwargs
        return None


if not TYPE_CHECKING:
    try:
        from cvcutter.domain.detection.audio_classifier import AudioContentClassifier
        from cvcutter.domain.detection.audio_energy import AudioEnergyDetector
        from cvcutter.domain.detection.visual_detector import VisualActivityDetector
    except ImportError:  # pragma: no cover - temporary fallback until detector module lands.
        AudioContentClassifier = None  # type: ignore[assignment]
        AudioEnergyDetector = None  # type: ignore[assignment]
        VisualActivityDetector = None  # type: ignore[assignment]

    try:
        from cvcutter.infrastructure.models.audio_classifier_runner import OnnxAudioClassifierRunner
    except Exception:  # pragma: no cover - optional runtime dependency/model.
        OnnxAudioClassifierRunner = None  # type: ignore[assignment]

    try:
        from cvcutter.infrastructure.models.yolo_runner import YoloModelRunner
    except Exception:  # pragma: no cover - optional runtime dependency/model.
        YoloModelRunner = None  # type: ignore[assignment]


class PipelineResourcesMixin:
    if TYPE_CHECKING:
        _active_config_hash: str | None
        _checkpoint_manager: CheckpointManager
        _logger: Any
        _project_store: ProjectStore
        _video_io: VideoIOService

    def _find_valid_checkpoint(
        self,
        project: ConcertProject,
        stage: PipelineStage,
        input_hashes: dict[str, str],
        model_versions: dict[str, str],
        segment_index: int | None = None,
    ) -> Checkpoint | None:
        """Locate the latest valid checkpoint for stage and optional segment index."""
        checkpoints = self._checkpoint_manager.load_all_checkpoints(self._project_id(project))
        config_snapshot = self._stage_config_snapshot(stage, project)
        for checkpoint in reversed(checkpoints):
            if checkpoint.stage != stage:
                continue
            if checkpoint.segment_index != segment_index:
                continue
            if self._checkpoint_manager.validate_checkpoint(
                checkpoint=checkpoint,
                current_input_hashes=input_hashes,
                current_config=config_snapshot,
                current_model_versions=model_versions,
            ):
                return checkpoint
        return None

    def _save_checkpoint(
        self,
        *,
        project: ConcertProject,
        stage: PipelineStage,
        input_hashes: dict[str, str],
        model_versions: dict[str, str],
        output_references: list[str],
        segment_index: int | None = None,
    ) -> Checkpoint:
        """Persist a checkpoint entity with standardized baseline metadata."""
        checkpoint = Checkpoint(
            id=uuid4(),
            project_id=self._project_id(project),
            stage=stage,
            status=CheckpointStatus.VALID,
            created_at=datetime.now(UTC),
            input_hashes=input_hashes,
            config_snapshot=self._stage_config_snapshot(stage, project),
            model_versions=model_versions,
            output_references=output_references,
            segment_index=segment_index,
        )
        self._checkpoint_manager.save_checkpoint(checkpoint)
        log_stage_transition(
            self._logger,
            stage.value,
            "CHECKPOINT_SAVED",
            checkpoint_id=str(checkpoint.id),
            input_refs=list(input_hashes),
            output_refs=output_references,
        )
        return checkpoint

    def _checkpoint_output_path(self, checkpoint: Checkpoint | None) -> Path | None:
        """Extract the first absolute output path from checkpoint references."""
        if checkpoint is None:
            return None
        for reference in checkpoint.output_references:
            path_candidate = Path(reference)
            if path_candidate.is_absolute():
                return path_candidate
        return None

    def _checkpoint_sync_offset(self, checkpoint: Checkpoint) -> float | None:
        """Parse sync-offset metadata from checkpoint output references."""
        for reference in checkpoint.output_references:
            if not reference.startswith("sync_offset:"):
                continue
            value = reference.split(":", 1)[1].strip()
            if value.lower() in {"none", ""}:
                return None
            try:
                return float(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _checkpoint_declares_zero_segments(checkpoint: Checkpoint | None) -> bool:
        """Return True when checkpoint metadata explicitly records zero detections."""
        if checkpoint is None:
            return False
        return "segments:0" in checkpoint.output_references

    @staticmethod
    def _project_id(project: ConcertProject) -> str:
        """Normalize project UUID for persistence and logging."""
        return str(project.id)

    @staticmethod
    def _config_snapshot(project: ConcertProject) -> dict[str, Any]:
        """Return deterministic dict representation of project config."""
        return asdict(project.config_snapshot)

    def _resume_input_hashes(self, project: ConcertProject) -> dict[str, Any]:
        """Build stage-scoped input hashes for resume-decision validation."""
        project_id = self._project_id(project)
        checkpoints = self._checkpoint_manager.load_all_checkpoints(project_id)
        scoped_inputs: dict[str, Any] = {PipelineStage.CONCATENATION.value: self._hash_source_inputs(project)}

        concat_checkpoint = self._latest_checkpoint_for_stage(checkpoints, PipelineStage.CONCATENATION)
        concat_path = self._checkpoint_output_path(concat_checkpoint)
        if concat_path is None:
            output_format = project.config_snapshot.output_format.strip(".") or "mp4"
            concat_path = project.output_directory / f"{self._project_id(project)}_concatenated.{output_format}"

        scoped_inputs[PipelineStage.DETECTION.value] = self._hash_for_concatenated_stage(concat_path)
        scoped_inputs[PipelineStage.AUDIO_SYNC.value] = self._hash_for_audio_sync_stage(project, concat_path)

        current_segments = self._project_store.load_segments(project_id)
        export_inputs: dict[str, dict[str, str]] = {}
        for segment in sorted(current_segments, key=lambda item: item.segment_index):
            export_inputs[f"segment:{segment.segment_index}"] = self._hash_for_export_stage(
                project,
                concat_path,
                segment,
            )
        if not export_inputs:
            for checkpoint in checkpoints:
                if checkpoint.stage != PipelineStage.EXPORT or checkpoint.segment_index is None:
                    continue
                if checkpoint.status != CheckpointStatus.VALID:
                    continue
                export_inputs[f"segment:{checkpoint.segment_index}"] = dict(checkpoint.input_hashes)
        if export_inputs:
            scoped_inputs[PipelineStage.EXPORT.value] = export_inputs

        return scoped_inputs

    def _resume_config_snapshots(self, project: ConcertProject) -> dict[str, dict[str, Any]]:
        """Build stage-scoped config snapshots for resume validation."""
        return {
            stage.value: self._stage_config_snapshot(stage, project)
            for stage in PipelineStage
        }

    def _resume_model_versions(self) -> dict[str, dict[str, str]]:
        """Build stage-scoped model-version mappings for resume validation."""
        return {stage.value: self._model_versions(stage) for stage in PipelineStage}

    @staticmethod
    def _resume_decision_reason(resume_decision: ResumeDecision) -> str:
        """Render resume decision details as a concise structured reason string."""
        resume_stage = resume_decision.resume_stage.value if resume_decision.resume_stage else "none"
        invalidated = ",".join(stage.value for stage in resume_decision.invalidated_stages) or "none"
        reasons = ";".join(
            f"{stage.value}:{reason}" for stage, reason in sorted(
                resume_decision.reasons.items(),
                key=lambda item: item[0].value,
            )
        ) or "none"
        return f"resume_stage={resume_stage}|invalidated={invalidated}|reasons={reasons}"

    @staticmethod
    def _latest_checkpoint_for_stage(
        checkpoints: list[Checkpoint],
        stage: PipelineStage,
    ) -> Checkpoint | None:
        """Return the latest valid stage-level checkpoint (segment_index is None)."""
        for checkpoint in reversed(checkpoints):
            if checkpoint.stage != stage:
                continue
            if checkpoint.segment_index is not None:
                continue
            if checkpoint.status != CheckpointStatus.VALID:
                continue
            return checkpoint
        return None

    def _apply_config_changes(self, project: ConcertProject, boundary_marker: str) -> None:
        """Apply persisted config updates at stage or segment boundaries only."""
        stored_project = self._project_store.load_project(self._project_id(project))
        if stored_project is None:
            return

        stored_snapshot = self._config_snapshot(stored_project)
        stored_hash = self._config_hash(stored_snapshot)
        if self._active_config_hash is None:
            self._active_config_hash = self._config_hash(self._config_snapshot(project))
        if stored_hash == self._active_config_hash:
            return

        previous_hash = self._active_config_hash
        project.config_snapshot = stored_project.config_snapshot
        self._active_config_hash = stored_hash
        self._project_store.save_project(project)
        log_stage_transition(
            self._logger,
            "PIPELINE",
            "CONFIG_APPLIED",
            decision="apply-next-boundary",
            decision_reason=f"{boundary_marker}:{previous_hash}->{stored_hash}",
        )

    @staticmethod
    def _config_hash(config_snapshot: dict[str, Any]) -> str:
        """Build deterministic config hash for boundary-change detection."""
        serialized = json.dumps(config_snapshot, sort_keys=True, ensure_ascii=False, default=str)
        return sha256(serialized.encode("utf-8")).hexdigest()

    def _stage_config_snapshot(
        self,
        stage: PipelineStage,
        project: ConcertProject,
    ) -> dict[str, Any]:
        """Build stage-scoped config snapshot used for checkpoint validation."""
        config = self._config_snapshot(project)
        stage_keys: dict[PipelineStage, set[str]] = {
            PipelineStage.CONCATENATION: {"output_format"},
            PipelineStage.DETECTION: {"enable_yolo_detection", "min_segment_duration_seconds"},
            PipelineStage.AUDIO_SYNC: {"audio_sync_sample_rate"},
            PipelineStage.EXPORT: {
                "enable_gpu",
                "mic_audio_volume",
                "output_format",
                "output_quality",
                "video_audio_volume",
            },
            PipelineStage.MAPPING: {"enable_gemini", "gemini_model", "mapping_review_threshold"},
            PipelineStage.UPLOAD: {"youtube_chunk_size"},
        }
        keys = stage_keys.get(stage, set())
        scoped = {key: config[key] for key in keys if key in config}
        return scoped or config

    def _hash_source_inputs(self, project: ConcertProject) -> dict[str, str]:
        """Compute stage input hashes for source-video dependent stages."""
        hashes: dict[str, str] = {}
        for source in sorted(project.source_videos, key=lambda item: item.order_index):
            fallback_hash = source.file_hash or f"missing::{source.file_path}"
            hashes[str(source.file_path)] = self._safe_file_hash(source.file_path, fallback_hash)
        return hashes

    def _hash_for_concatenated_stage(self, concatenated_path: Path) -> dict[str, str]:
        """Compute stage input hashes for stages driven by concatenated video."""
        fallback_hash = f"missing::{concatenated_path}"
        return {str(concatenated_path): self._safe_file_hash(concatenated_path, fallback_hash)}

    def _hash_for_audio_sync_stage(
        self,
        project: ConcertProject,
        concatenated_path: Path,
    ) -> dict[str, str]:
        """Compute stage input hashes for audio synchronization."""
        hashes = self._hash_for_concatenated_stage(concatenated_path)
        if project.external_audio is not None:
            fallback_hash = project.external_audio.file_hash or f"missing::{project.external_audio.file_path}"
            hashes[str(project.external_audio.file_path)] = self._safe_file_hash(
                project.external_audio.file_path,
                fallback_hash,
            )
        return hashes

    def _hash_for_export_stage(
        self,
        project: ConcertProject,
        concatenated_path: Path,
        segment: PerformanceSegment,
    ) -> dict[str, str]:
        """Compute stage input hashes for per-segment export checkpoints."""
        hashes = self._hash_for_audio_sync_stage(project, concatenated_path)
        hashes[f"segment:{segment.segment_index}"] = (
            f"{segment.start_time_seconds:.6f}:{segment.end_time_seconds:.6f}"
        )
        return hashes

    def _safe_file_hash(self, file_path: Path, fallback: str) -> str:
        """Compute a file hash while tolerating transient file-access failures."""
        try:
            return compute_file_hash(file_path)
        except OSError:
            self._logger.warning("Failed to hash file %s; using fallback hash marker.", file_path)
            return fallback

    def _model_versions(
        self,
        stage: PipelineStage,
        *,
        detector: AudioEnergyDetector | None = None,
    ) -> dict[str, str]:
        """Return deterministic model/version identifiers per stage."""
        if stage == PipelineStage.DETECTION:
            del detector
            return {
                "composite_detector": "CompositeDetector",
                "audio_energy_detector": "AudioEnergyDetector",
                "audio_classifier": "OnnxAudioClassifierRunner",
                "visual_detector": "YoloModelRunner",
                "audio_classifier_runtime": (
                    "available" if self._audio_classifier_available() else "unavailable"
                ),
                "visual_detector_runtime": (
                    "available" if self._visual_detector_available() else "unavailable"
                ),
            }
        if stage == PipelineStage.AUDIO_SYNC:
            return {"audio_sync": "compute_sync_offset"}
        if stage in {PipelineStage.CONCATENATION, PipelineStage.EXPORT}:
            return {"video_io": self._video_io.__class__.__name__}
        return {"pipeline": "baseline"}

    def _build_audio_classifier_channel(self) -> AudioContentClassifier | None:
        """Build domain-level audio classifier channel when ONNX model is available."""
        if AudioContentClassifier is None or OnnxAudioClassifierRunner is None:
            return None

        model_path = self._audio_classifier_model_path()
        if model_path is None:
            return None
        try:
            runner = OnnxAudioClassifierRunner(model_path=model_path)
            return AudioContentClassifier(model_runner=runner)
        except Exception as exc:
            self._logger.warning("Audio classifier unavailable; continuing without classifier channel: %s", exc)
            return None

    def _build_visual_detector_channel(
        self,
        project: ConcertProject,
    ) -> tuple[VisualActivityDetector | None, str | None]:
        """Build visual detector channel or return a runtime fallback reason."""
        if not project.config_snapshot.enable_yolo_detection:
            return None, None
        if VisualActivityDetector is None or YoloModelRunner is None:
            return None, "YOLO_RUNTIME_UNAVAILABLE"

        model_path = self._yolo_model_path()
        if model_path is None:
            return None, "YOLO_MODEL_NOT_FOUND"
        try:
            runner = YoloModelRunner(model_path=model_path)
            return VisualActivityDetector(model_runner=runner), None
        except Exception as exc:
            self._logger.warning("YOLO unavailable at runtime; falling back to audio-only detection: %s", exc)
            return None, str(exc)

    @staticmethod
    def _audio_classifier_model_path() -> Path | None:
        relative_candidates = (
            Path("audio_classifier.onnx"),
            Path("models") / "audio_classifier.onnx",
            Path("models") / "audio-classifier.onnx",
            Path("assets") / "audio_classifier.onnx",
        )
        for root in PipelineResourcesMixin._runtime_roots():
            for relative in relative_candidates:
                candidate = root / relative
                if candidate.exists():
                    return candidate
        return None

    @staticmethod
    def _yolo_model_path() -> Path | None:
        relative_candidates = (
            Path("yolov8n.pt"),
            Path("models") / "yolov8n.pt",
        )
        for root in PipelineResourcesMixin._runtime_roots():
            for relative in relative_candidates:
                candidate = root / relative
                if candidate.exists():
                    return candidate
        return None

    @staticmethod
    def _runtime_roots() -> list[Path]:
        """Resolve candidate roots for source and PyInstaller one-file runtime."""
        roots: list[Path] = [Path.cwd(), Path(__file__).resolve().parents[3]]
        frozen_root = getattr(sys, "_MEIPASS", None)
        if isinstance(frozen_root, str) and frozen_root.strip():
            roots.append(Path(frozen_root))
        unique_roots: list[Path] = []
        for root in roots:
            if root in unique_roots:
                continue
            unique_roots.append(root)
        return unique_roots

    def _audio_classifier_available(self) -> bool:
        return OnnxAudioClassifierRunner is not None and self._audio_classifier_model_path() is not None

    def _visual_detector_available(self) -> bool:
        return YoloModelRunner is not None and self._yolo_model_path() is not None

    @staticmethod
    def _detection_mode_counts(segments: list[PerformanceSegment]) -> dict[str, int]:
        """Count output segments by effective detection mode."""
        counts: dict[str, int] = {}
        for segment in segments:
            counts[segment.effective_detection_mode] = counts.get(segment.effective_detection_mode, 0) + 1
        return counts

    def _invoke_audio_energy_detector(
        self,
        detector: AudioEnergyDetector,
        concatenated_path: Path,
        min_segment_duration_seconds: float,
    ) -> list[Any]:
        """Invoke detector with flexible argument compatibility across implementations."""
        call_specs = (
            ((concatenated_path,), {"min_segment_duration_seconds": min_segment_duration_seconds}),
            ((concatenated_path,), {"min_duration_seconds": min_segment_duration_seconds}),
            ((concatenated_path,), {}),
            ((str(concatenated_path),), {"min_segment_duration_seconds": min_segment_duration_seconds}),
            ((str(concatenated_path),), {}),
        )

        for method_name in ("detect_boundaries", "detect", "run"):
            method = getattr(detector, method_name, None)
            if not callable(method):
                continue
            for args, kwargs in call_specs:
                try:
                    result = method(*args, **kwargs)
                    return self._coerce_boundary_result(result)
                except TypeError:
                    continue

        if callable(detector):
            for args, kwargs in call_specs:
                try:
                    result = detector(*args, **kwargs)
                    return self._coerce_boundary_result(result)
                except TypeError:
                    continue
        return []

    @staticmethod
    def _coerce_boundary_result(result: Any) -> list[Any]:
        """Normalize raw detector call outputs to a list."""
        if result is None:
            return []
        if isinstance(result, list):
            return result
        if isinstance(result, tuple):
            return list(result)
        if isinstance(result, (str, bytes, bytearray)):
            return []
        if hasattr(result, "__iter__"):
            return list(result)
        return []

    def _normalize_boundaries(
        self,
        boundaries: Iterable[Any],
        minimum_duration_seconds: float,
    ) -> list[tuple[float, float, float]]:
        """Normalize heterogeneous detector outputs into stable boundary tuples."""
        normalized: list[tuple[float, float, float]] = []
        for item in boundaries:
            coerced = self._coerce_boundary(item)
            if coerced is None:
                continue
            start_seconds, end_seconds, confidence = coerced
            if end_seconds - start_seconds < minimum_duration_seconds:
                continue
            normalized.append((start_seconds, end_seconds, confidence))
        normalized.sort(key=lambda segment: segment[0])
        return normalized

    @staticmethod
    def _coerce_boundary(boundary: Any) -> tuple[float, float, float] | None:
        """Parse one detector boundary payload into (start, end, confidence)."""
        start_raw: Any
        end_raw: Any
        confidence_raw: Any = 0.75

        if isinstance(boundary, dict):
            start_raw = boundary.get("start_time_seconds", boundary.get("start_seconds", boundary.get("start")))
            end_raw = boundary.get("end_time_seconds", boundary.get("end_seconds", boundary.get("end")))
            confidence_raw = boundary.get("confidence", boundary.get("score", 0.75))
        elif isinstance(boundary, (tuple, list)):
            if len(boundary) < 2:
                return None
            start_raw = boundary[0]
            end_raw = boundary[1]
            confidence_raw = boundary[2] if len(boundary) >= 3 else 0.75
        else:
            start_raw = getattr(
                boundary,
                "start_time_seconds",
                getattr(boundary, "start_seconds", getattr(boundary, "start", None)),
            )
            end_raw = getattr(
                boundary,
                "end_time_seconds",
                getattr(boundary, "end_seconds", getattr(boundary, "end", None)),
            )
            confidence_raw = getattr(boundary, "confidence", getattr(boundary, "score", 0.75))

        try:
            start_seconds = float(start_raw)
            end_seconds = float(end_raw)
            confidence = max(0.0, min(1.0, float(confidence_raw)))
        except (TypeError, ValueError):
            return None
        if start_seconds < 0 or end_seconds <= start_seconds:
            return None
        return start_seconds, end_seconds, confidence

    def _invoke_sync_offset(
        self,
        *,
        concatenated_path: Path,
        external_audio_path: Path,
        sample_rate: int,
    ) -> float | None:
        """Invoke sync-offset computation with broad compatibility for function signatures."""
        call_specs = (
            (
                (),
                {
                    "video_path": concatenated_path,
                    "external_audio_path": external_audio_path,
                    "sample_rate": sample_rate,
                },
            ),
            (
                (),
                {
                    "haystack_path": external_audio_path,
                    "needle_path": concatenated_path,
                    "target_sr": sample_rate,
                },
            ),
            ((concatenated_path, external_audio_path, sample_rate), {}),
            ((external_audio_path, concatenated_path, sample_rate), {}),
            ((external_audio_path, concatenated_path), {"sample_rate": sample_rate}),
            ((concatenated_path, external_audio_path), {"sample_rate": sample_rate}),
        )

        for args, kwargs in call_specs:
            try:
                result = compute_sync_offset(*args, **kwargs)
            except TypeError:
                continue
            normalized = self._normalize_sync_result(result)
            if normalized is not None:
                return normalized
        return None

    @staticmethod
    def _normalize_sync_result(result: Any) -> float | None:
        """Normalize sync result payloads to a single float offset in seconds."""
        if result is None:
            return None
        if isinstance(result, (int, float)):
            return float(result)
        if isinstance(result, dict):
            offset = result.get("offset_seconds", result.get("sync_offset_seconds", result.get("offset")))
            try:
                return None if offset is None else float(offset)
            except (TypeError, ValueError):
                return None
        offset_attr = getattr(result, "offset_seconds", getattr(result, "sync_offset_seconds", None))
        try:
            return None if offset_attr is None else float(offset_attr)
        except (TypeError, ValueError):
            return None

    def _build_audio_mix(
        self,
        project: ConcertProject,
        sync_offset: float | None,
    ) -> AudioMixConfig | None:
        """Build audio mixing configuration when external audio is available."""
        if project.external_audio is None or sync_offset is None:
            return None
        return AudioMixConfig(
            video_volume=project.config_snapshot.video_audio_volume,
            mic_volume=project.config_snapshot.mic_audio_volume,
            mic_audio_path=project.external_audio.file_path,
            sync_offset_seconds=sync_offset,
        )

    def _resolve_exported_output(
        self,
        segment: PerformanceSegment,
        checkpoint: Checkpoint | None,
    ) -> Path | None:
        """Resolve existing exported file path from segment data or checkpoint metadata."""
        if checkpoint is not None and segment.exported_file_path is not None:
            return segment.exported_file_path
        if checkpoint is None:
            return None
        for reference in checkpoint.output_references:
            if reference.startswith("segments:") or reference.startswith("sync_offset:"):
                continue
            candidate = Path(reference)
            if candidate.is_absolute():
                return candidate
        return None

    def _segment_output_path(self, project: ConcertProject, segment: PerformanceSegment) -> Path:
        """Build deterministic exported output path for a segment."""
        safe_project_name = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in project.name.strip()
        ).strip("_")
        if not safe_project_name:
            safe_project_name = self._project_id(project)
        extension = project.config_snapshot.output_format.strip(".") or "mp4"
        filename = f"{safe_project_name}_segment_{segment.segment_index + 1:03d}.{extension}"
        return project.output_directory / filename

    def _validate_export_disk_space(self, project: ConcertProject, concatenated_path: Path) -> None:
        """Reject export when free space is below the required 2x source threshold."""
        disk_probe = getattr(self._video_io, "get_disk_space", None)
        if not callable(disk_probe):
            return

        try:
            disk_info = disk_probe(project.output_directory)
        except Exception:
            self._logger.warning("Disk-space preflight check unavailable; continuing without guard.")
            return

        free_bytes: int | None = None
        disk_path = project.output_directory
        if isinstance(disk_info, DiskSpaceInfo):
            free_bytes = int(disk_info.free_bytes)
            disk_path = disk_info.path
        else:
            free_raw = getattr(disk_info, "free_bytes", None)
            path_raw = getattr(disk_info, "path", project.output_directory)
            if isinstance(free_raw, (int, float)):
                free_bytes = int(free_raw)
            if isinstance(path_raw, Path):
                disk_path = path_raw

        if free_bytes is None:
            self._logger.warning("Disk-space preflight payload missing free_bytes; continuing without guard.")
            return

        required_bytes = self._required_export_free_space_bytes(project, concatenated_path)
        if free_bytes < required_bytes:
            raise RuntimeError(
                "Insufficient disk space for export: "
                f"required={required_bytes} bytes, available={free_bytes} bytes at {disk_path}.",
            )

    @staticmethod
    def _calculate_throughput_eta_seconds(
        *,
        bytes_processed: int,
        elapsed_seconds: float,
        total_bytes: int,
    ) -> float | None:
        """Calculate remaining ETA from throughput (bytes_processed / elapsed_seconds)."""
        if bytes_processed <= 0 or elapsed_seconds <= 0 or total_bytes <= 0:
            return None
        throughput = bytes_processed / elapsed_seconds
        if throughput <= 0:
            return None
        remaining_bytes = max(total_bytes - bytes_processed, 0)
        if remaining_bytes == 0:
            return 0.0
        return remaining_bytes / throughput

    def _emit_export_progress(
        self,
        current: int,
        total: int,
        *,
        progress_callback: Callable[[ProgressEvent], None] | None,
        stage: str,
        segment_index: int,
        total_segments: int,
        bytes_before: int,
        export_started_at: float,
        estimated_total_bytes: int,
    ) -> None:
        """Emit export progress enriched with throughput-based ETA information."""
        bytes_done = bytes_before + max(0, min(current, total))
        eta_seconds = self._calculate_throughput_eta_seconds(
            bytes_processed=bytes_done,
            elapsed_seconds=perf_counter() - export_started_at,
            total_bytes=estimated_total_bytes,
        )
        eta_suffix = f" ETA {eta_seconds:.1f}s" if eta_seconds is not None else ""
        self._emit_progress(
            progress_callback,
            stage,
            current,
            total,
            f"Exporting segment {segment_index + 1}/{total_segments}.{eta_suffix}",
        )

    @staticmethod
    def _required_export_free_space_bytes(project: ConcertProject, concatenated_path: Path) -> int:
        """Return required free bytes for export preflight (>= 2x source baseline)."""
        source_bytes = 0
        for source_video in project.source_videos:
            source_size = source_video.file_size_bytes
            if source_size <= 0 and source_video.file_path.exists():
                source_size = source_video.file_path.stat().st_size
            source_bytes += max(source_size, 0)
        concatenated_bytes = concatenated_path.stat().st_size if concatenated_path.exists() else 0
        baseline = max(source_bytes, concatenated_bytes, 1)
        return baseline * 2

    def _estimate_export_total_bytes(
        self,
        project: ConcertProject,
        segments: list[PerformanceSegment],
        concatenated_path: Path,
    ) -> int:
        """Estimate export total bytes for throughput-based ETA reporting."""
        source_size = concatenated_path.stat().st_size if concatenated_path.exists() else 0
        if source_size <= 0:
            source_size = sum(max(video.file_size_bytes, 0) for video in project.source_videos)
        source_size = max(source_size, 1)

        total_source_duration = sum(max(video.duration_seconds, 0.0) for video in project.source_videos)
        total_segment_duration = sum(
            max(segment.end_time_seconds - segment.start_time_seconds, 0.0)
            for segment in segments
        )
        if total_source_duration <= 0:
            duration_ratio = 1.0
        else:
            duration_ratio = max(total_segment_duration / total_source_duration, 0.05)
        return max(1, int(source_size * duration_ratio))

    def _cleanup_temporary_artifacts(self, project: ConcertProject, concatenated_path: Path) -> None:
        """Apply FR-046 cleanup policy after successful export completion."""
        cleaned_items: list[str] = []

        if concatenated_path.exists():
            try:
                concatenated_path.unlink()
                cleaned_items.append(str(concatenated_path))
            except OSError:
                self._logger.warning("Failed to remove temporary concatenated file: %s", concatenated_path)

        cleaned_checkpoint_count = 0
        checkpoint_store = getattr(self._checkpoint_manager, "_checkpoint_store", None)
        if checkpoint_store is not None and hasattr(checkpoint_store, "clean_completed"):
            try:
                cleaned_checkpoint_count = int(checkpoint_store.clean_completed(self._project_id(project)))
            except Exception:
                cleaned_checkpoint_count = 0

        output_refs = list(cleaned_items)
        if cleaned_checkpoint_count:
            output_refs.append(f"cleaned_checkpoints:{cleaned_checkpoint_count}")
        log_stage_transition(
            self._logger,
            PipelineStage.EXPORT.value,
            "CLEANUP_COMPLETED",
            output_refs=output_refs,
            decision="auto-clean",
            decision_reason="FR-046",
        )

    def _safe_gpu_check(self) -> bool:
        """Return GPU availability while tolerating adapter errors."""
        try:
            return self._video_io.check_gpu_available()
        except Exception:
            return False

    @staticmethod
    def _emit_progress(
        callback: Callable[[ProgressEvent], None] | None,
        stage: str,
        current: int,
        total: int,
        message: str,
    ) -> None:
        """Emit one progress event when callback is supplied."""
        if callback is None:
            return
        event = ProgressEvent(stage=stage, current=current, total=total, message=message)
        callback(event)
