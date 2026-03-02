"""Unit tests for baseline domain models used in User Story 1."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import DetectionSignal, PerformanceSegment
from cvcutter.shared.types import ExportStatus, ProcessingState, SignalType
from tests.conftest import make_project_config, make_project_id, make_segment_dict


def _make_source_video(file_path: Path, *, order_index: int = 0) -> SourceVideo:
    now = datetime.now(UTC)
    return SourceVideo(
        id=make_project_id(),
        file_path=file_path,
        order_index=order_index,
        duration_seconds=120.0,
        resolution=(1920, 1080),
        codec="h264",
        creation_timestamp=now,
        file_hash="video-hash",
        file_size_bytes=2048,
    )


def _make_project(tmp_path: Path, *, state: ProcessingState = ProcessingState.CREATED) -> ConcertProject:
    source_path = tmp_path / f"source-{make_project_id()}.mp4"
    source_path.write_bytes(b"\x00" * 64)
    now = datetime.now(UTC)
    return ConcertProject(
        id=UUID(make_project_id()),
        name="baseline-project",
        event_date=None,
        venue="main-hall",
        source_videos=[_make_source_video(source_path)],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=tmp_path / "output",
        config_snapshot=ProjectConfig(**make_project_config()),
        processing_state=state,
        created_at=now,
        updated_at=now,
    )


def _make_segment(
    *,
    segment_index: int = 0,
    start_time: float = 0.0,
    end_time: float = 120.0,
    detection_mode: str = "full",
) -> PerformanceSegment:
    raw = make_segment_dict(
        segment_index=segment_index,
        start_time=start_time,
        end_time=end_time,
        detection_mode=detection_mode,
    )
    return PerformanceSegment(
        id=UUID(str(raw["id"])),
        segment_index=int(raw["segment_index"]),
        start_time_seconds=float(raw["start_time_seconds"]),
        end_time_seconds=float(raw["end_time_seconds"]),
        detection_confidence=float(raw["detection_confidence"]),
        effective_detection_mode=str(raw["effective_detection_mode"]),
        detection_signals=[],
        fallback_reason=(str(raw["fallback_reason"]) if raw["fallback_reason"] else None),
        exported_file_path=None,
        export_status=ExportStatus(str(raw["export_status"])),
        user_adjusted=bool(raw["user_adjusted"]),
    )


def test_concert_project_state_transitions_to_ready_for_export(tmp_path: Path) -> None:
    project = _make_project(tmp_path)

    for state in (
        ProcessingState.CONCATENATING,
        ProcessingState.DETECTING,
        ProcessingState.SYNCING_AUDIO,
        ProcessingState.READY_FOR_EXPORT,
    ):
        project.transition_to(state)
        assert project.processing_state == state


def test_concert_project_invalid_state_transition_raises_value_error(tmp_path: Path) -> None:
    project = _make_project(tmp_path)

    with pytest.raises(ValueError, match="Invalid state transition"):
        project.transition_to(ProcessingState.READY_FOR_EXPORT)


def test_paused_can_be_entered_from_any_active_state(tmp_path: Path) -> None:
    active_states = (
        ProcessingState.CREATED,
        ProcessingState.CONCATENATING,
        ProcessingState.DETECTING,
        ProcessingState.SYNCING_AUDIO,
        ProcessingState.READY_FOR_EXPORT,
        ProcessingState.EXPORTING,
        ProcessingState.MAPPING,
        ProcessingState.READY_FOR_UPLOAD,
        ProcessingState.UPLOADING,
    )

    for state in active_states:
        project = _make_project(tmp_path, state=state)
        project.transition_to(ProcessingState.PAUSED)
        assert project.processing_state == ProcessingState.PAUSED


def test_failed_can_be_entered_from_any_active_state(tmp_path: Path) -> None:
    active_states = (
        ProcessingState.CREATED,
        ProcessingState.CONCATENATING,
        ProcessingState.DETECTING,
        ProcessingState.SYNCING_AUDIO,
        ProcessingState.READY_FOR_EXPORT,
        ProcessingState.EXPORTING,
        ProcessingState.MAPPING,
        ProcessingState.READY_FOR_UPLOAD,
        ProcessingState.UPLOADING,
    )

    for state in active_states:
        project = _make_project(tmp_path, state=state)
        project.transition_to(ProcessingState.FAILED)
        assert project.processing_state == ProcessingState.FAILED


def test_source_video_validation_with_nonexistent_path_for_type_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    import cvcutter.domain.models.project as project_models

    monkeypatch.setattr(project_models, "_validate_existing_file", lambda *_: None)
    source = SourceVideo(
        id=make_project_id(),
        file_path=Path(r"C:\non-existent\video.mp4"),
        order_index=0,
        duration_seconds=10.0,
        resolution=(1280, 720),
        codec="h264",
        creation_timestamp=datetime.now(UTC),
        file_hash="source-hash",
        file_size_bytes=1000,
    )

    assert isinstance(source.file_path, Path)
    assert isinstance(source.order_index, int)
    assert isinstance(source.duration_seconds, float)


def test_project_config_defaults() -> None:
    config = ProjectConfig()
    defaults = make_project_config()

    for key, value in defaults.items():
        assert getattr(config, key) == value


def test_performance_segment_adjust_boundary_updates_times_and_marks_user_adjusted() -> None:
    segment = _make_segment(start_time=5.0, end_time=95.0)

    segment.adjust_boundary(10.0, 90.0)

    assert segment.start_time_seconds == 10.0
    assert segment.end_time_seconds == 90.0
    assert segment.user_adjusted is True


def test_performance_segment_split_segment_creates_two_segments_and_reassigns_indices() -> None:
    segment = _make_segment(segment_index=2, start_time=0.0, end_time=120.0)

    first, second = segment.split_segment(60.0)

    assert first.segment_index == 2
    assert second.segment_index == 3
    assert first.start_time_seconds == 0.0
    assert first.end_time_seconds == 60.0
    assert second.start_time_seconds == 60.0
    assert second.end_time_seconds == 120.0
    assert first.user_adjusted is True
    assert second.user_adjusted is True


@pytest.mark.parametrize("split_time", [0.0, 120.0, -1.0, 130.0])
def test_split_validation_requires_split_time_between_segment_bounds(split_time: float) -> None:
    segment = _make_segment(start_time=0.0, end_time=120.0)

    with pytest.raises(ValueError):
        segment.split_segment(split_time)


def test_detection_signal_validation() -> None:
    signal = DetectionSignal(
        signal_type=SignalType.AUDIO_ENERGY,
        confidence=0.8,
        start_time_seconds=10.0,
        end_time_seconds=20.0,
        metadata={"window": "test"},
    )
    assert signal.signal_type == SignalType.AUDIO_ENERGY

    with pytest.raises(ValueError, match=r"confidence must be between 0\.0 and 1\.0"):
        DetectionSignal(
            signal_type=SignalType.AUDIO_CLASSIFIER,
            confidence=1.2,
            start_time_seconds=10.0,
            end_time_seconds=20.0,
            metadata={},
        )

    with pytest.raises(ValueError, match="end_time_seconds must be greater than start_time_seconds"):
        DetectionSignal(
            signal_type=SignalType.VISUAL_YOLO,
            confidence=0.4,
            start_time_seconds=5.0,
            end_time_seconds=5.0,
            metadata={},
        )


@pytest.mark.xfail(reason="Minimum segment duration enforcement is not implemented yet.")
def test_segment_minimum_duration_enforcement() -> None:
    minimum = float(make_project_config()["min_segment_duration_seconds"])

    with pytest.raises(ValueError):
        _make_segment(start_time=0.0, end_time=minimum - 0.1)
