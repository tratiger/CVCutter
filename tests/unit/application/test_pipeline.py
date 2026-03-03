"""Unit tests for pipeline resume/restart and checkpoint behavior."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime
from types import MethodType
from typing import TYPE_CHECKING
from unittest import mock
from uuid import uuid4

import pytest

from cvcutter.application.checkpoint_manager import ResumeDecision
from cvcutter.application.pipeline import PipelineOrchestrator
from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import DetectionSignal, PerformanceSegment
from cvcutter.shared.types import (
    CheckpointStatus,
    PipelineStage,
    ProcessingState,
    SignalType,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_active_job_guard() -> None:
    """Reset process-level pipeline concurrency guard between tests."""
    PipelineOrchestrator._active_job_project_id = None
    PipelineOrchestrator._active_job_owner = None
    yield
    PipelineOrchestrator._active_job_project_id = None
    PipelineOrchestrator._active_job_owner = None


def _make_project(tmp_path: Path, *, output_quality: str = "high") -> ConcertProject:
    now = datetime.now(UTC)
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"stub-input-video")
    source = SourceVideo(
        id=str(uuid4()),
        file_path=source_path,
        order_index=0,
        duration_seconds=120.0,
        resolution=(1920, 1080),
        codec="h264",
        creation_timestamp=now,
        file_hash="source-file-hash",
        file_size_bytes=source_path.stat().st_size,
    )
    return ConcertProject(
        id=uuid4(),
        name="unit-test-project",
        event_date=None,
        venue=None,
        source_videos=[source],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=tmp_path / "exports",
        config_snapshot=ProjectConfig(output_quality=output_quality),
        processing_state=ProcessingState.CREATED,
        created_at=now,
        updated_at=now,
    )


def _clone_with_quality(project: ConcertProject, *, output_quality: str) -> ConcertProject:
    return ConcertProject(
        id=project.id,
        name=project.name,
        event_date=project.event_date,
        venue=project.venue,
        source_videos=project.source_videos,
        external_audio=project.external_audio,
        program_pdf_path=project.program_pdf_path,
        form_source_path=project.form_source_path,
        form_remote_id=project.form_remote_id,
        form_remote_sheet_id=project.form_remote_sheet_id,
        output_directory=project.output_directory,
        config_snapshot=ProjectConfig(output_quality=output_quality),
        processing_state=project.processing_state,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _make_segment(index: int, *, start: float, end: float) -> PerformanceSegment:
    signal = DetectionSignal(
        signal_type=SignalType.AUDIO_ENERGY,
        confidence=0.9,
        start_time_seconds=start,
        end_time_seconds=end,
        metadata={"source": "test"},
    )
    return PerformanceSegment(
        id=uuid4(),
        segment_index=index,
        start_time_seconds=start,
        end_time_seconds=end,
        detection_confidence=0.9,
        effective_detection_mode="audio_only",
        detection_signals=[signal],
        fallback_reason="AUDIO_ENERGY_BASELINE",
    )


def _make_checkpoint(
    project: ConcertProject,
    *,
    stage: PipelineStage,
    input_hashes: dict[str, str],
    model_versions: dict[str, str],
    output_references: list[str],
    segment_index: int | None = None,
) -> Checkpoint:
    return Checkpoint(
        id=uuid4(),
        project_id=str(project.id),
        stage=stage,
        status=CheckpointStatus.VALID,
        created_at=datetime.now(UTC),
        input_hashes=dict(input_hashes),
        config_snapshot=asdict(project.config_snapshot),
        model_versions=dict(model_versions),
        output_references=list(output_references),
        segment_index=segment_index,
    )


def _build_orchestrator(
    project: ConcertProject,
    *,
    checkpoints: list[Checkpoint] | None = None,
    preloaded_segments: list[PerformanceSegment] | None = None,
    change_config_after_first_export: bool = False,
) -> tuple[PipelineOrchestrator, mock.Mock, mock.Mock, mock.Mock, list[Checkpoint], list[str]]:
    saved_checkpoints = list(checkpoints or [])
    persisted_segments = list(preloaded_segments or [])
    export_qualities: list[str] = []
    config_changed = {"value": False}
    changed_project = _clone_with_quality(project, output_quality="low")

    video_io = mock.Mock()

    def _concatenate(
        video_paths: list[Path],
        output_path: Path,
        progress_callback=None,
    ) -> Path:
        del video_paths
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"concatenated")
        if progress_callback is not None:
            progress_callback(1, 1)
        return output_path

    def _export_segment(
        *,
        source_path: Path,
        output_path: Path,
        start_seconds: float,
        end_seconds: float,
        audio_mix=None,
        quality: str = "high",
        use_gpu: bool = False,
        progress_callback=None,
    ) -> Path:
        del source_path, start_seconds, end_seconds, audio_mix, use_gpu
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("segment", encoding="utf-8")
        export_qualities.append(quality)
        if progress_callback is not None:
            progress_callback(1, 1)
        if change_config_after_first_export and len(export_qualities) == 1:
            config_changed["value"] = True
        return output_path

    video_io.concatenate.side_effect = _concatenate
    video_io.export_segment.side_effect = _export_segment
    video_io.check_gpu_available.return_value = False

    checkpoint_manager = mock.Mock()
    checkpoint_manager.save_checkpoint.side_effect = saved_checkpoints.append
    checkpoint_manager.load_all_checkpoints.side_effect = lambda project_id: [
        checkpoint
        for checkpoint in saved_checkpoints
        if checkpoint.project_id == project_id
    ]

    def _config_matches(saved_config: dict, current_config: dict) -> bool:
        if set(current_config).issubset(saved_config):
            return {key: saved_config[key] for key in current_config} == current_config
        return saved_config == current_config

    checkpoint_manager.validate_checkpoint.side_effect = (
        lambda checkpoint, current_input_hashes, current_config, current_model_versions: (
            checkpoint.status == CheckpointStatus.VALID
            and checkpoint.input_hashes == current_input_hashes
            and _config_matches(checkpoint.config_snapshot, current_config)
            and checkpoint.model_versions == current_model_versions
        )
    )

    def _invalidate_with_cascade(project_id: str, stage: PipelineStage, segment_index: int | None = None) -> list[str]:
        del project_id, stage, segment_index
        invalidated_ids: list[str] = []
        for checkpoint in saved_checkpoints:
            checkpoint.status = CheckpointStatus.INVALIDATED
            invalidated_ids.append(str(checkpoint.id))
        return invalidated_ids

    checkpoint_manager.invalidate_with_cascade.side_effect = _invalidate_with_cascade
    checkpoint_manager.make_resume_decision.return_value = ResumeDecision(
        can_resume=True,
        resume_stage=PipelineStage.CONCATENATION,
        invalidated_stages=[],
        reasons={},
    )

    project_store = mock.Mock()
    project_store.save_project.side_effect = lambda project_value: None
    project_store.save_segments.side_effect = lambda project_id, segments: persisted_segments.clear() or persisted_segments.extend(segments)
    project_store.load_segments.side_effect = lambda project_id: list(persisted_segments)
    project_store.load_project.side_effect = lambda project_id: (
        changed_project if config_changed["value"] else project
    )

    orchestrator = PipelineOrchestrator(
        video_io=video_io,
        checkpoint_manager=checkpoint_manager,
        project_store=project_store,
    )

    def _stub_run_detection(
        self: PipelineOrchestrator,
        project_value: ConcertProject,
        concatenated_path: Path,
        progress_callback,
    ) -> list[PerformanceSegment]:
        del progress_callback
        detected = [_make_segment(0, start=0.0, end=40.0), _make_segment(1, start=45.0, end=90.0)]
        self._project_store.save_segments(self._project_id(project_value), detected)
        self._save_checkpoint(
            project=project_value,
            stage=PipelineStage.DETECTION,
            input_hashes=self._hash_for_concatenated_stage(concatenated_path),
            model_versions=self._model_versions(PipelineStage.DETECTION),
            output_references=[f"segments:{len(detected)}"],
        )
        return detected

    orchestrator._run_detection = MethodType(_stub_run_detection, orchestrator)
    return orchestrator, video_io, checkpoint_manager, project_store, saved_checkpoints, export_qualities


def test_pipeline_writes_stage_and_segment_checkpoints(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    orchestrator, _, _, _, saved_checkpoints, _ = _build_orchestrator(project)

    orchestrator.run(project)

    assert [checkpoint.stage for checkpoint in saved_checkpoints[:3]] == [
        PipelineStage.CONCATENATION,
        PipelineStage.DETECTION,
        PipelineStage.AUDIO_SYNC,
    ]
    export_checkpoints = [item for item in saved_checkpoints if item.stage == PipelineStage.EXPORT]
    assert [item.segment_index for item in export_checkpoints] == [0, 1]


def test_resume_skips_stages_with_valid_checkpoints(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    orchestrator, video_io, checkpoint_manager, _, saved_checkpoints, _ = _build_orchestrator(project)

    concatenated_path = project.output_directory / f"{project.id}_concatenated.mp4"
    concatenated_path.parent.mkdir(parents=True, exist_ok=True)
    concatenated_path.write_bytes(b"concatenated")
    segments = [_make_segment(0, start=0.0, end=40.0), _make_segment(1, start=45.0, end=90.0)]
    for segment in segments:
        export_path = project.output_directory / f"segment_{segment.segment_index:03d}.mp4"
        export_path.write_text("exported", encoding="utf-8")

    concat_hashes = orchestrator._hash_source_inputs(project)
    detection_hashes = orchestrator._hash_for_concatenated_stage(concatenated_path)
    audio_hashes = orchestrator._hash_for_audio_sync_stage(project, concatenated_path)
    saved_checkpoints.extend(
        [
            _make_checkpoint(
                project,
                stage=PipelineStage.CONCATENATION,
                input_hashes=concat_hashes,
                model_versions={"video_io": video_io.__class__.__name__},
                output_references=[str(concatenated_path)],
            ),
                _make_checkpoint(
                    project,
                    stage=PipelineStage.DETECTION,
                    input_hashes=detection_hashes,
                    model_versions=orchestrator._model_versions(PipelineStage.DETECTION),
                    output_references=[f"segments:{len(segments)}"],
                ),
            _make_checkpoint(
                project,
                stage=PipelineStage.AUDIO_SYNC,
                input_hashes=audio_hashes,
                model_versions={"audio_sync": "compute_sync_offset"},
                output_references=["sync_offset:none"],
            ),
        ],
    )
    for segment in segments:
        export_path = project.output_directory / f"segment_{segment.segment_index:03d}.mp4"
        saved_checkpoints.append(
            _make_checkpoint(
                project,
                stage=PipelineStage.EXPORT,
                input_hashes=orchestrator._hash_for_export_stage(project, concatenated_path, segment),
                model_versions={"video_io": video_io.__class__.__name__},
                output_references=[str(export_path)],
                segment_index=segment.segment_index,
            ),
        )

    checkpoint_manager.make_resume_decision.return_value = ResumeDecision(
        can_resume=True,
        resume_stage=PipelineStage.CONCATENATION,
        invalidated_stages=[],
        reasons={PipelineStage.CONCATENATION: "valid_checkpoint_available"},
    )
    project_store = orchestrator._project_store
    project_store.load_segments.side_effect = lambda project_id: list(segments)
    detection_checkpoint_count_before = len(
        [item for item in saved_checkpoints if item.stage == PipelineStage.DETECTION],
    )
    audio_sync_checkpoint_count_before = len(
        [item for item in saved_checkpoints if item.stage == PipelineStage.AUDIO_SYNC],
    )

    orchestrator.resume(project)

    assert video_io.concatenate.call_count == 0
    assert video_io.export_segment.call_count == 0
    assert len([item for item in saved_checkpoints if item.stage == PipelineStage.DETECTION]) == (
        detection_checkpoint_count_before
    )
    assert len([item for item in saved_checkpoints if item.stage == PipelineStage.AUDIO_SYNC]) == (
        audio_sync_checkpoint_count_before
    )
    checkpoint_manager.make_resume_decision.assert_called_once()


def test_restart_reexecutes_all_stages_from_scratch(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    orchestrator, video_io, checkpoint_manager, _, saved_checkpoints, _ = _build_orchestrator(project)

    stale_checkpoint = _make_checkpoint(
        project,
        stage=PipelineStage.CONCATENATION,
        input_hashes={"stale": "hash"},
        model_versions={"video_io": video_io.__class__.__name__},
        output_references=[str(project.output_directory / "stale_concatenated.mp4")],
    )
    saved_checkpoints.append(stale_checkpoint)

    orchestrator.restart(project)

    checkpoint_manager.invalidate_with_cascade.assert_called_once_with(
        str(project.id),
        PipelineStage.CONCATENATION,
    )
    assert video_io.concatenate.call_count == 1
    assert video_io.export_segment.call_count == 2


def test_resume_reexports_segments_when_export_checkpoints_are_missing(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    orchestrator, video_io, checkpoint_manager, project_store, saved_checkpoints, _ = _build_orchestrator(project)

    concatenated_path = project.output_directory / f"{project.id}_concatenated.mp4"
    concatenated_path.parent.mkdir(parents=True, exist_ok=True)
    concatenated_path.write_bytes(b"concatenated")
    segments = [_make_segment(0, start=0.0, end=40.0), _make_segment(1, start=45.0, end=90.0)]
    for segment in segments:
        stale_export = project.output_directory / f"stale_{segment.segment_index}.mp4"
        stale_export.write_text("stale", encoding="utf-8")
        segment.exported_file_path = stale_export

    saved_checkpoints.extend(
        [
            _make_checkpoint(
                project,
                stage=PipelineStage.CONCATENATION,
                input_hashes=orchestrator._hash_source_inputs(project),
                model_versions={"video_io": video_io.__class__.__name__},
                output_references=[str(concatenated_path)],
            ),
            _make_checkpoint(
                project,
                stage=PipelineStage.DETECTION,
                input_hashes=orchestrator._hash_for_concatenated_stage(concatenated_path),
                model_versions=orchestrator._model_versions(PipelineStage.DETECTION),
                output_references=[f"segments:{len(segments)}"],
            ),
            _make_checkpoint(
                project,
                stage=PipelineStage.AUDIO_SYNC,
                input_hashes=orchestrator._hash_for_audio_sync_stage(project, concatenated_path),
                model_versions={"audio_sync": "compute_sync_offset"},
                output_references=["sync_offset:none"],
            ),
        ],
    )

    checkpoint_manager.make_resume_decision.return_value = ResumeDecision(
        can_resume=True,
        resume_stage=PipelineStage.CONCATENATION,
        invalidated_stages=[],
        reasons={},
    )
    project_store.load_segments.side_effect = lambda project_id: list(segments)

    orchestrator.resume(project)

    assert video_io.export_segment.call_count == len(segments)


def test_pipeline_prevents_concurrent_runs(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    orchestrator, _, _, _, _, _ = _build_orchestrator(project)
    PipelineOrchestrator._active_job_project_id = "another-project"

    with pytest.raises(RuntimeError, match="already active"):
        orchestrator.run(project)


def test_config_changes_apply_on_next_segment_boundary(
    tmp_path: Path,
) -> None:
    project = _make_project(tmp_path, output_quality="high")
    orchestrator, _, _, _, _, export_qualities = _build_orchestrator(
        project,
        change_config_after_first_export=True,
    )

    orchestrator.run(project)

    assert export_qualities == ["high", "low"]


def test_stale_cancel_request_does_not_fail_next_pipeline_run(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    orchestrator, _, _, _, _, _ = _build_orchestrator(project)

    orchestrator.cancel()
    result = orchestrator.run(project)

    assert result.processing_state != ProcessingState.FAILED


def test_cancel_from_secondary_instance_targets_active_pipeline_owner(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    owner, _, _, _, _, _ = _build_orchestrator(project)
    controller, _, _, _, _, _ = _build_orchestrator(project)
    PipelineOrchestrator._active_job_project_id = str(project.id)
    PipelineOrchestrator._active_job_owner = owner

    controller.cancel()

    assert owner._cancel_requested is True
    assert controller._cancel_requested is False


def test_cancel_request_after_owner_acquire_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _make_project(tmp_path)
    owner, _, _, _, _, _ = _build_orchestrator(project)
    controller, _, _, _, _, _ = _build_orchestrator(project)
    owner_acquired = threading.Event()
    saw_cancel: dict[str, bool] = {"value": False}

    original_acquire = PipelineOrchestrator._acquire_active_job.__func__

    def wrapped_acquire(
        cls: type[PipelineOrchestrator],
        project_id: str,
        orchestrator_owner: PipelineOrchestrator,
    ) -> None:
        original_acquire(cls, project_id, orchestrator_owner)
        if orchestrator_owner is owner:
            owner_acquired.set()
            time.sleep(0.1)

    def fake_run_pipeline(self: PipelineOrchestrator, run_project, progress_callback=None):
        del progress_callback
        saw_cancel["value"] = self._cancel_requested
        return run_project

    monkeypatch.setattr(PipelineOrchestrator, "_acquire_active_job", classmethod(wrapped_acquire))
    monkeypatch.setattr(PipelineOrchestrator, "_run_pipeline", fake_run_pipeline)

    run_thread = threading.Thread(target=owner.run, args=(project,))
    run_thread.start()
    assert owner_acquired.wait(timeout=2.0)
    controller.cancel()
    run_thread.join(timeout=2.0)

    assert saw_cancel["value"] is True


def test_cancel_during_last_export_segment_is_honored_before_completion(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    owner, video_io, _, _, _, _ = _build_orchestrator(project)
    controller, _, _, _, _, _ = _build_orchestrator(project)
    original_export = video_io.export_segment.side_effect

    def _export_with_late_cancel(**kwargs):
        exported = original_export(**kwargs)
        if "segment_001" in str(kwargs["output_path"]):
            controller.cancel()
        return exported

    video_io.export_segment.side_effect = _export_with_late_cancel

    result = owner.run(project)

    assert result.processing_state == ProcessingState.FAILED
