"""Integration checks for resume observability and structured logging (T097)."""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime
from types import MethodType
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from cvcutter.application.checkpoint_manager import CheckpointManager, ResumeDecision
from cvcutter.application.pipeline import PipelineOrchestrator
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.services.types import DiskSpaceInfo
from cvcutter.infrastructure.logging.structured_logger import JsonFormatter
from cvcutter.shared.types import CheckpointStatus, PipelineStage, ProcessingState

if TYPE_CHECKING:
    from cvcutter.domain.models.checkpoint import Checkpoint

pytestmark = pytest.mark.integration


class _LocalVideoIO:
    def concatenate(self, video_paths, output_path, progress_callback=None):
        del video_paths
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"concatenated-local")
        if progress_callback is not None:
            progress_callback(1, 1)
        return output_path

    def export_segment(
        self,
        *,
        source_path,
        output_path,
        start_seconds,
        end_seconds,
        audio_mix=None,
        quality="high",
        use_gpu=False,
        progress_callback=None,
    ):
        del source_path, start_seconds, end_seconds, audio_mix, quality, use_gpu
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("segment-bytes", encoding="utf-8")
        if progress_callback is not None:
            progress_callback(1, 1)
        return output_path

    def check_gpu_available(self):
        return False

    def get_disk_space(self, path):
        return DiskSpaceInfo(total_bytes=10_000_000, free_bytes=9_000_000, path=path)


class _MemoryProjectStore:
    def __init__(self) -> None:
        self._project: ConcertProject | None = None
        self._segments: dict[str, list[PerformanceSegment]] = {}

    def save_project(self, project: ConcertProject) -> None:
        self._project = project

    def load_project(self, project_id: str) -> ConcertProject | None:
        if self._project is None:
            return None
        if str(self._project.id) != project_id:
            return None
        return self._project

    def save_segments(self, project_id: str, segments: list[PerformanceSegment]) -> None:
        self._segments[project_id] = list(segments)

    def load_segments(self, project_id: str) -> list[PerformanceSegment]:
        return list(self._segments.get(project_id, []))


class _MemoryCheckpointManager:
    def __init__(self) -> None:
        self.saved: list[Checkpoint] = []
        self.resume_decision = ResumeDecision(
            can_resume=True,
            resume_stage=PipelineStage.CONCATENATION,
            invalidated_stages=[],
            reasons={PipelineStage.CONCATENATION: "valid_checkpoint_available"},
        )

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        self.saved.append(checkpoint)

    def load_all_checkpoints(self, project_id: str) -> list[Checkpoint]:
        return [checkpoint for checkpoint in self.saved if checkpoint.project_id == project_id]

    def validate_checkpoint(
        self,
        checkpoint: Checkpoint,
        current_input_hashes: dict,
        current_config: dict,
        current_model_versions: dict,
    ) -> bool:
        if checkpoint.status != CheckpointStatus.VALID:
            return False
        if checkpoint.input_hashes != current_input_hashes:
            return False
        if set(current_config).issubset(checkpoint.config_snapshot):
            snapshot = {key: checkpoint.config_snapshot[key] for key in current_config}
        else:
            snapshot = checkpoint.config_snapshot
        if snapshot != current_config:
            return False
        return checkpoint.model_versions == current_model_versions

    def make_resume_decision(
        self,
        project_id: str,
        current_input_hashes: dict,
        current_config: dict,
        current_model_versions: dict,
    ) -> ResumeDecision:
        del project_id, current_input_hashes, current_config, current_model_versions
        return self.resume_decision

    def invalidate_with_cascade(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None = None,
    ) -> list[str]:
        del stage, segment_index
        invalidated: list[str] = []
        for checkpoint in self.saved:
            if checkpoint.project_id != project_id:
                continue
            checkpoint.status = CheckpointStatus.INVALIDATED
            invalidated.append(str(checkpoint.id))
        return invalidated


class _InvalidationStore:
    def save(self, checkpoint: Checkpoint) -> None:
        del checkpoint

    def load(self, project_id: str, stage: PipelineStage, segment_index: int | None = None) -> Checkpoint | None:
        del project_id, stage, segment_index
        return None

    def load_all(self, project_id: str) -> list[Checkpoint]:
        del project_id
        return []

    def invalidate(
        self,
        project_id: str,
        stage: PipelineStage,
        segment_index: int | None = None,
        cascade: bool = True,
    ) -> list[str]:
        del project_id, segment_index, cascade
        return [f"{stage.value.lower()}-checkpoint"]

    def clean_completed(self, project_id: str) -> int:
        del project_id
        return 0


@pytest.fixture
def structured_logger_capture():
    stream = io.StringIO()
    logger = logging.getLogger(f"tests.integration.resume_observability.{uuid4()}")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    def _records() -> list[dict[str, object]]:
        lines = [line for line in stream.getvalue().splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    try:
        yield logger, _records
    finally:
        handler.close()
        logger.handlers = []
        logger.propagate = True


@pytest.fixture
def project(tmp_path):
    now = datetime.now(UTC)
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"\x00" * 4096)
    source = SourceVideo(
        id=str(uuid4()),
        file_path=source_path,
        order_index=0,
        duration_seconds=120.0,
        resolution=(1920, 1080),
        codec="h264",
        creation_timestamp=now,
        file_hash="source-hash",
        file_size_bytes=source_path.stat().st_size,
    )
    return ConcertProject(
        id=uuid4(),
        name="resume-observability",
        event_date=None,
        venue=None,
        source_videos=[source],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=tmp_path / "exports",
        config_snapshot=ProjectConfig(),
        processing_state=ProcessingState.CREATED,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def orchestrator(project, structured_logger_capture):
    logger, read_records = structured_logger_capture
    checkpoint_manager = _MemoryCheckpointManager()
    project_store = _MemoryProjectStore()
    project_store.save_project(project)
    orchestrator = PipelineOrchestrator(
        video_io=_LocalVideoIO(),
        checkpoint_manager=checkpoint_manager,
        project_store=project_store,
        logger=logger,
    )

    def _stub_run_detection(self, project_value, concatenated_path, progress_callback):
        del progress_callback
        detected = [
            PerformanceSegment(
                id=uuid4(),
                segment_index=0,
                start_time_seconds=0.0,
                end_time_seconds=55.0,
                detection_confidence=0.9,
                effective_detection_mode="full",
                detection_signals=[],
            ),
        ]
        project_id = self._project_id(project_value)
        self._project_store.save_segments(project_id, detected)
        self._save_checkpoint(
            project=project_value,
            stage=PipelineStage.DETECTION,
            input_hashes=self._hash_for_concatenated_stage(concatenated_path),
            model_versions=self._model_versions(PipelineStage.DETECTION),
            output_references=["segments:1"],
        )
        return detected

    orchestrator._run_detection = MethodType(_stub_run_detection, orchestrator)
    return orchestrator, checkpoint_manager, read_records


def test_structured_logging_captures_stage_transitions_with_checkpoint_ids(project, orchestrator) -> None:
    pipeline, _, read_records = orchestrator

    pipeline.run(project)
    records = read_records()
    checkpoint_events = [record for record in records if record.get("event") == "CHECKPOINT_SAVED"]

    assert checkpoint_events
    assert all(record.get("checkpoint_id") for record in checkpoint_events)
    assert {
        PipelineStage.CONCATENATION.value,
        PipelineStage.DETECTION.value,
        PipelineStage.AUDIO_SYNC.value,
        PipelineStage.EXPORT.value,
    }.issubset({str(record.get("pipeline_stage")) for record in checkpoint_events})


def test_resume_traceability_logs_validation_decision_links(project, orchestrator) -> None:
    pipeline, checkpoint_manager, read_records = orchestrator
    before = len(read_records())
    checkpoint_manager.resume_decision = ResumeDecision(
        can_resume=False,
        resume_stage=None,
        invalidated_stages=[PipelineStage.DETECTION, PipelineStage.EXPORT],
        reasons={
            PipelineStage.DETECTION: "config_hash_mismatch",
            PipelineStage.EXPORT: "invalidated_by_detection",
        },
    )

    pipeline.resume(project)
    new_records = read_records()[before:]
    decision_log = next(record for record in new_records if record.get("event") == "RESUME_DECISION")
    point_log = next(record for record in new_records if record.get("event") == "RESUME_POINT")
    decision_reason = str(decision_log.get("decision_reason"))

    assert decision_log["decision"] == "restart"
    assert "resume_stage=none" in decision_reason
    assert "DETECTION:config_hash_mismatch" in decision_reason
    assert "EXPORT:invalidated_by_detection" in decision_reason
    assert point_log["decision_reason"] == decision_reason


def test_invalidation_reasons_are_logged_with_human_readable_detail(caplog) -> None:
    manager = CheckpointManager(_InvalidationStore())

    with caplog.at_level(logging.INFO, logger="cvcutter.application.checkpoint_manager"):
        manager.invalidate_with_cascade("project-observe", PipelineStage.DETECTION, segment_index=2)

    merged = "\n".join(caplog.messages)
    assert "Cascade invalidation requested" in merged
    assert "project_id=project-observe" in merged
    assert "stage=DETECTION" in merged
    assert "segment_index=2" in merged
    assert "targets=['DETECTION', 'EXPORT', 'MAPPING', 'UPLOAD']" in merged
