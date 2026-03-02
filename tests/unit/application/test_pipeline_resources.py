"""Unit tests for pipeline disk preflight and throughput ETA behavior (T086)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

import pytest

from cvcutter.application.pipeline import PipelineOrchestrator
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.services.types import DiskSpaceInfo
from cvcutter.shared.types import ProcessingState


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
