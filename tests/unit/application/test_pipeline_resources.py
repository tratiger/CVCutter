"""Unit tests for pipeline disk preflight and throughput ETA behavior (T086)."""

from __future__ import annotations

import functools
from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

import pytest

from cvcutter.application.pipeline import PipelineOrchestrator
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.services.types import DiskSpaceInfo
from cvcutter.shared.types import PipelineStage, ProcessingState


def _make_project(tmp_path) -> ConcertProject:
    now = datetime.now(UTC)
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"\x00" * 512)
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
        name="resource-test",
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


def test_export_disk_preflight_rejects_when_free_space_is_insufficient(tmp_path) -> None:
    """Pipeline should reject export when free space is below the 2x source requirement."""
    project = _make_project(tmp_path)
    concatenated_path = tmp_path / "concatenated.mp4"
    concatenated_path.write_bytes(b"\x00" * 1024)

    video_io = mock.Mock()
    video_io.get_disk_space.return_value = DiskSpaceInfo(
        total_bytes=10_000,
        free_bytes=100,
        path=tmp_path,
    )
    orchestrator = PipelineOrchestrator(
        video_io=video_io,
        checkpoint_manager=mock.Mock(),
        project_store=mock.Mock(),
    )

    with pytest.raises(RuntimeError, match="Insufficient disk space"):
        orchestrator._validate_export_disk_space(project, concatenated_path)


def test_throughput_eta_calculation_accuracy() -> None:
    """ETA should be derived from bytes-processed throughput and remaining bytes."""
    eta_seconds = PipelineOrchestrator._calculate_throughput_eta_seconds(
        bytes_processed=2_000,
        elapsed_seconds=10.0,
        total_bytes=5_000,
    )
    assert eta_seconds == pytest.approx(15.0)


def test_detection_model_versions_keep_legacy_default_runner_names(tmp_path) -> None:
    _ = _make_project(tmp_path)
    orchestrator = PipelineOrchestrator(
        video_io=mock.Mock(),
        checkpoint_manager=mock.Mock(),
        project_store=mock.Mock(),
    )

    versions = orchestrator._model_versions(PipelineStage.DETECTION)

    assert versions["audio_classifier"] == "OnnxAudioClassifierRunner"
    assert versions["visual_detector"] == "YoloModelRunner"


def test_runner_factories_support_keyword_only_model_path(tmp_path) -> None:
    project = _make_project(tmp_path)
    onnx_path = tmp_path / "audio_classifier.onnx"
    yolo_path = tmp_path / "yolov8n.pt"
    onnx_path.write_bytes(b"onnx")
    yolo_path.write_bytes(b"yolo")

    class _KeywordOnlyAudioRunner:
        def __init__(self, *, model_path):
            self._model_path = model_path

        def classify(self, audio_chunk):
            del audio_chunk
            return []

        def model_version(self) -> str:
            return f"audio:{self._model_path.name}"

    class _KeywordOnlyVisualRunner:
        def __init__(self, *, model_path):
            self._model_path = model_path

        def detect(self, frame):
            del frame
            return []

        def model_version(self) -> str:
            return f"visual:{self._model_path.name}"

    orchestrator = PipelineOrchestrator(
        video_io=mock.Mock(),
        checkpoint_manager=mock.Mock(),
        project_store=mock.Mock(),
        audio_classifier_runner_factory=_KeywordOnlyAudioRunner,
        visual_runner_factory=_KeywordOnlyVisualRunner,
    )

    with (
        mock.patch.object(PipelineOrchestrator, "_audio_classifier_model_path", return_value=onnx_path),
        mock.patch.object(PipelineOrchestrator, "_yolo_model_path", return_value=yolo_path),
    ):
        audio_channel = orchestrator._build_audio_classifier_channel()
        visual_channel, visual_reason = orchestrator._build_visual_detector_channel(project)

    assert audio_channel is not None
    assert visual_channel is not None
    assert visual_reason is None


def test_model_versions_include_partial_factory_identity(tmp_path) -> None:
    def _audio_factory(*, model_path, variant: str) -> object:
        del model_path
        return object()

    partial_factory = functools.partial(_audio_factory, variant="v1")
    orchestrator = PipelineOrchestrator(
        video_io=mock.Mock(),
        checkpoint_manager=mock.Mock(),
        project_store=mock.Mock(),
        audio_classifier_runner_factory=partial_factory,
    )

    versions = orchestrator._model_versions(PipelineStage.DETECTION)

    assert versions["audio_classifier"].startswith("partial(")
    assert "variant='v1'" in versions["audio_classifier"]
