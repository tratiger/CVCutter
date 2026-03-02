"""Integration scaffolding for baseline load-to-export workflow (T022)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter, sleep
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.shared.types import CheckpointStatus, PipelineStage
from tests.conftest import make_project_config, make_project_id, make_segment_dict

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@dataclass
class _StubVideoIOAdapter:
    concatenate_calls: list[tuple[list[Path], Path]] = field(default_factory=list)
    export_calls: list[tuple[Path, Path, float, float]] = field(default_factory=list)
    export_delay_seconds: float = 0.0

    def concatenate(
        self,
        video_paths: list[Path],
        output_path: Path,
        progress_callback=None,
    ) -> Path:
        del progress_callback
        self.concatenate_calls.append((list(video_paths), output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"stub-concatenated-video")
        return output_path

    def export_segment(
        self,
        source_path: Path,
        output_path: Path,
        start_seconds: float,
        end_seconds: float,
        audio_mix=None,
        quality: str = "high",
        use_gpu: bool = False,
        progress_callback=None,
    ) -> Path:
        del audio_mix, quality, use_gpu, progress_callback
        if self.export_delay_seconds > 0:
            sleep(self.export_delay_seconds)
        self.export_calls.append((source_path, output_path, start_seconds, end_seconds))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{start_seconds:.2f}-{end_seconds:.2f}", encoding="utf-8")
        return output_path


@dataclass
class _StubBoundaryDetector:
    segment_bounds: list[tuple[float, float]]

    def detect(self, concatenated_path: Path) -> list[tuple[float, float]]:
        assert concatenated_path.exists()
        return list(self.segment_bounds)


@dataclass
class _StubCheckpointStore:
    saved: list[Checkpoint] = field(default_factory=list)
    clean_completed_calls: list[str] = field(default_factory=list)

    def save(self, checkpoint: Checkpoint) -> None:
        self.saved.append(checkpoint)

    def has_export_checkpoint(self, project_id: str, segment_index: int) -> bool:
        return any(
            checkpoint.project_id == project_id
            and checkpoint.stage == PipelineStage.EXPORT
            and checkpoint.segment_index == segment_index
            and checkpoint.status == CheckpointStatus.VALID
            for checkpoint in self.saved
        )

    def clear_project(self, project_id: str) -> None:
        self.saved = [checkpoint for checkpoint in self.saved if checkpoint.project_id != project_id]

    def clean_completed(self, project_id: str) -> int:
        self.clean_completed_calls.append(project_id)
        return 1


@dataclass
class _PipelineRunResult:
    concatenated_path: Path
    detected_segments: list[tuple[float, float]]
    exported_paths: list[Path]


class _BaselineProcessingPipeline:
    def __init__(
        self,
        *,
        video_io: _StubVideoIOAdapter,
        detector: _StubBoundaryDetector,
        checkpoint_store: _StubCheckpointStore,
        project_id: str,
        temp_dir: Path,
        auto_clean_success: bool,
    ) -> None:
        self.video_io = video_io
        self.detector = detector
        self.checkpoint_store = checkpoint_store
        self.project_id = project_id
        self.temp_dir = temp_dir
        self.auto_clean_success = auto_clean_success

    def run(
        self,
        source_videos: list[Path],
        output_dir: Path,
        *,
        stop_after_exports: int | None = None,
        resume_mode: bool = False,
    ) -> _PipelineRunResult:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        concatenated_path = self.temp_dir / "concatenated.mp4"
        self.video_io.concatenate(source_videos, concatenated_path)
        self.checkpoint_store.save(_make_checkpoint(self.project_id, PipelineStage.CONCATENATION))

        detected_segments = self.detector.detect(concatenated_path)
        exported_paths: list[Path] = []
        completed_exports = 0
        for index, (start, end) in enumerate(detected_segments):
            export_path = output_dir / f"segment_{index:03d}.mp4"
            if (
                resume_mode
                and export_path.exists()
                and self.checkpoint_store.has_export_checkpoint(self.project_id, index)
            ):
                exported_paths.append(export_path)
                continue
            self.video_io.export_segment(concatenated_path, export_path, start, end)
            exported_paths.append(export_path)
            self.checkpoint_store.save(
                _make_checkpoint(
                    self.project_id,
                    PipelineStage.EXPORT,
                    segment_index=index,
                ),
            )
            completed_exports += 1
            if stop_after_exports is not None and completed_exports >= stop_after_exports:
                raise InterruptedError(f"Forced interruption after {completed_exports} export(s).")

        self.checkpoint_store.clean_completed(self.project_id)
        if self.auto_clean_success and concatenated_path.exists():
            concatenated_path.unlink()

        return _PipelineRunResult(
            concatenated_path=concatenated_path,
            detected_segments=detected_segments,
            exported_paths=exported_paths,
        )

    def resume(self, source_videos: list[Path], output_dir: Path) -> _PipelineRunResult:
        return self.run(source_videos, output_dir, resume_mode=True)

    def restart(self, source_videos: list[Path], output_dir: Path) -> _PipelineRunResult:
        self.checkpoint_store.clear_project(self.project_id)
        for export_path in output_dir.glob("segment_*.mp4"):
            export_path.unlink()
        return self.run(source_videos, output_dir)


def _make_checkpoint(
    project_id: str,
    stage: PipelineStage,
    *,
    segment_index: int | None = None,
) -> Checkpoint:
    return Checkpoint(
        id=uuid4(),
        project_id=project_id,
        stage=stage,
        status=CheckpointStatus.VALID,
        created_at=datetime.now(UTC),
        input_hashes={"source": "hash"},
        config_snapshot=make_project_config(),
        model_versions={"stub-pipeline": "v1"},
        output_references=[],
        segment_index=segment_index,
    )


def _build_pipeline(
    tmp_path: Path,
    segment_bounds: list[tuple[float, float]],
    *,
    auto_clean_success: bool,
    export_delay_seconds: float = 0.0,
) -> tuple[_BaselineProcessingPipeline, _StubVideoIOAdapter, _StubCheckpointStore]:
    video_io = _StubVideoIOAdapter(export_delay_seconds=export_delay_seconds)
    detector = _StubBoundaryDetector(segment_bounds=segment_bounds)
    checkpoint_store = _StubCheckpointStore()
    pipeline = _BaselineProcessingPipeline(
        video_io=video_io,
        detector=detector,
        checkpoint_store=checkpoint_store,
        project_id=make_project_id(),
        temp_dir=tmp_path / "temp",
        auto_clean_success=auto_clean_success,
    )
    return pipeline, video_io, checkpoint_store


@pytest.fixture
def source_videos(tmp_path: Path) -> list[Path]:
    paths: list[Path] = []
    for index in range(2):
        source = tmp_path / f"source-{index}.mp4"
        source.write_bytes(b"\x00" * 1024)
        paths.append(source)
    return paths


@pytest.fixture
def baseline_segment_bounds() -> list[tuple[float, float]]:
    first = make_segment_dict(segment_index=0, start_time=0.0, end_time=40.0)
    second = make_segment_dict(segment_index=1, start_time=55.0, end_time=110.0)
    return [
        (float(first["start_time_seconds"]), float(first["end_time_seconds"])),
        (float(second["start_time_seconds"]), float(second["end_time_seconds"])),
    ]


def test_load_to_export_workflow_scaffold(source_videos: list[Path], tmp_path: Path) -> None:
    pipeline, _, _ = _build_pipeline(
        tmp_path,
        segment_bounds=[(0.0, 30.0), (45.0, 90.0)],
        auto_clean_success=False,
    )

    result = pipeline.run(source_videos, tmp_path / "exports")

    assert result.detected_segments
    assert len(result.detected_segments) == len(result.exported_paths)


def test_pipeline_creates_concatenated_output_from_source_videos(
    source_videos: list[Path],
    baseline_segment_bounds: list[tuple[float, float]],
    tmp_path: Path,
) -> None:
    pipeline, video_io, _ = _build_pipeline(
        tmp_path,
        segment_bounds=baseline_segment_bounds,
        auto_clean_success=False,
    )

    result = pipeline.run(source_videos, tmp_path / "exports")

    assert video_io.concatenate_calls
    assert result.concatenated_path.exists()
    assert result.concatenated_path.read_bytes() == b"stub-concatenated-video"


def test_baseline_boundary_detection_produces_segments(
    source_videos: list[Path],
    baseline_segment_bounds: list[tuple[float, float]],
    tmp_path: Path,
) -> None:
    pipeline, _, _ = _build_pipeline(
        tmp_path,
        segment_bounds=baseline_segment_bounds,
        auto_clean_success=False,
    )

    result = pipeline.run(source_videos, tmp_path / "exports")

    assert result.detected_segments
    assert all(end > start for start, end in result.detected_segments)


def test_segments_can_be_exported_with_proper_format(
    source_videos: list[Path],
    baseline_segment_bounds: list[tuple[float, float]],
    tmp_path: Path,
) -> None:
    pipeline, _, _ = _build_pipeline(
        tmp_path,
        segment_bounds=baseline_segment_bounds,
        auto_clean_success=False,
    )

    result = pipeline.run(source_videos, tmp_path / "exports")

    assert result.exported_paths
    assert all(path.suffix == ".mp4" for path in result.exported_paths)
    assert all(path.exists() for path in result.exported_paths)


def test_pipeline_writes_per_segment_export_checkpoints(
    source_videos: list[Path],
    baseline_segment_bounds: list[tuple[float, float]],
    tmp_path: Path,
) -> None:
    pipeline, _, checkpoint_store = _build_pipeline(
        tmp_path,
        segment_bounds=baseline_segment_bounds,
        auto_clean_success=False,
    )

    result = pipeline.run(source_videos, tmp_path / "exports")

    export_checkpoints = [item for item in checkpoint_store.saved if item.stage == PipelineStage.EXPORT]
    assert len(export_checkpoints) == len(result.detected_segments)
    assert [item.segment_index for item in export_checkpoints] == list(
        range(len(result.detected_segments)),
    )


def test_successful_run_applies_fr046_auto_clean_behavior(
    source_videos: list[Path],
    baseline_segment_bounds: list[tuple[float, float]],
    tmp_path: Path,
) -> None:
    pipeline, _, checkpoint_store = _build_pipeline(
        tmp_path,
        segment_bounds=baseline_segment_bounds,
        auto_clean_success=True,
    )

    result = pipeline.run(source_videos, tmp_path / "exports")

    assert not result.concatenated_path.exists()
    assert checkpoint_store.clean_completed_calls == [pipeline.project_id]


def test_forced_interruption_then_resume_continues_from_next_incomplete_segment(
    source_videos: list[Path],
    baseline_segment_bounds: list[tuple[float, float]],
    tmp_path: Path,
) -> None:
    pipeline, video_io, _ = _build_pipeline(
        tmp_path,
        segment_bounds=baseline_segment_bounds,
        auto_clean_success=False,
    )
    output_dir = tmp_path / "exports"

    with pytest.raises(InterruptedError):
        pipeline.run(source_videos, output_dir, stop_after_exports=1)

    resumed = pipeline.resume(source_videos, output_dir)

    assert len(video_io.export_calls) == 2
    assert resumed.exported_paths
    assert all(path.exists() for path in resumed.exported_paths)


def test_restart_from_scratch_reexports_all_segments(
    source_videos: list[Path],
    baseline_segment_bounds: list[tuple[float, float]],
    tmp_path: Path,
) -> None:
    pipeline, video_io, _ = _build_pipeline(
        tmp_path,
        segment_bounds=baseline_segment_bounds,
        auto_clean_success=False,
    )
    output_dir = tmp_path / "exports"

    with pytest.raises(InterruptedError):
        pipeline.run(source_videos, output_dir, stop_after_exports=1)

    export_calls_before_restart = len(video_io.export_calls)
    restarted = pipeline.restart(source_videos, output_dir)

    assert len(restarted.exported_paths) == len(baseline_segment_bounds)
    assert len(video_io.export_calls) == export_calls_before_restart + len(baseline_segment_bounds)


def test_sc004_resumed_processing_is_less_than_half_of_full_reprocess_time(
    source_videos: list[Path],
    tmp_path: Path,
) -> None:
    segment_bounds = [(0.0, 25.0), (30.0, 55.0), (60.0, 85.0), (90.0, 115.0)]
    full_pipeline, _, _ = _build_pipeline(
        tmp_path / "full",
        segment_bounds=segment_bounds,
        auto_clean_success=False,
        export_delay_seconds=0.2,
    )
    output_dir_full = tmp_path / "full" / "exports"
    full_start = perf_counter()
    full_pipeline.run(source_videos, output_dir_full)
    full_duration = perf_counter() - full_start

    resume_pipeline, _, _ = _build_pipeline(
        tmp_path / "resume",
        segment_bounds=segment_bounds,
        auto_clean_success=False,
        export_delay_seconds=0.2,
    )
    output_dir_resume = tmp_path / "resume" / "exports"
    with pytest.raises(InterruptedError):
        resume_pipeline.run(source_videos, output_dir_resume, stop_after_exports=3)

    resume_start = perf_counter()
    resume_pipeline.resume(source_videos, output_dir_resume)
    resumed_duration = perf_counter() - resume_start

    assert resumed_duration < (full_duration * 0.5)
