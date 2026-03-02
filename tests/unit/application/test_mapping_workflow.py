"""Unit tests for mapping workflow orchestration and checkpoint semantics (T106)."""

from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from cvcutter.application.mapping_workflow import MappingWorkflow, MappingWorkflowState
from cvcutter.domain.mapping import CompositeMapper
from cvcutter.domain.models.metadata import FormResponse, ProgramEntry, VideoMetadataMapping
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.shared.types import (
    CheckpointStatus,
    MatchMethod,
    PipelineStage,
    PrivacySetting,
    ProcessingState,
)

if TYPE_CHECKING:
    from pathlib import Path

    from cvcutter.domain.models.checkpoint import Checkpoint


class _ProjectStoreStub:
    def __init__(self) -> None:
        self.mappings_by_project: dict[str, list[VideoMetadataMapping]] = {}
        self.saved_projects: list[ConcertProject] = []

    def save_mappings(self, project_id: str, mappings: list[VideoMetadataMapping]) -> None:
        self.mappings_by_project[project_id] = copy.deepcopy(mappings)

    def save_project(self, project: ConcertProject) -> None:
        self.saved_projects.append(project)


class _CheckpointStoreStub:
    def __init__(self) -> None:
        self.saved: list[Checkpoint] = []

    def save(self, checkpoint: Checkpoint) -> None:
        self.saved.append(checkpoint)


class _LookupStub:
    def lookup(self, title: str, composer: str | None = None, performers: list[str] | None = None) -> list:
        del title, composer, performers
        return []

    def is_available(self) -> bool:
        return True

    def dictionary_revision(self) -> str:
        return "stub"


def _make_project(tmp_path: Path, *, state: ProcessingState = ProcessingState.MAPPING) -> ConcertProject:
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"\x00" * 64)
    now = datetime.now(UTC)
    source_video = SourceVideo(
        id=str(uuid4()),
        file_path=source_path,
        order_index=0,
        duration_seconds=120.0,
        resolution=(1920, 1080),
        codec="h264",
        creation_timestamp=now,
        file_hash="video-hash",
        file_size_bytes=source_path.stat().st_size,
    )
    return ConcertProject(
        id=uuid4(),
        name="mapping-workflow-test",
        event_date=None,
        venue="hall",
        source_videos=[source_video],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=tmp_path / "output",
        config_snapshot=ProjectConfig(),
        processing_state=state,
        created_at=now,
        updated_at=now,
    )


def _make_segment(index: int) -> PerformanceSegment:
    return PerformanceSegment(
        id=uuid4(),
        segment_index=index,
        start_time_seconds=float(index * 60),
        end_time_seconds=float(index * 60 + 45),
        detection_confidence=0.9,
        effective_detection_mode="full",
        detection_signals=[],
    )


def _make_entry(order: int, title: str) -> ProgramEntry:
    return ProgramEntry(
        id=f"entry-{order}",
        order_number=order,
        piece_title=title,
        composer=None,
        performer_names=[],
        ensemble=None,
        instrument=None,
        raw_text=title,
    )


def test_mapping_workflow_state_transitions(tmp_path: Path) -> None:
    project_store = _ProjectStoreStub()
    checkpoint_store = _CheckpointStoreStub()
    workflow = MappingWorkflow(project_store, checkpoint_store, mapper=CompositeMapper())
    project = _make_project(tmp_path)

    assert workflow.state == MappingWorkflowState.IDLE

    workflow.auto_map(
        project=project,
        segments=[_make_segment(0)],
        entries=[_make_entry(1, "Moonlight Sonata")],
        form_responses=[],
        transcription_results=[],
        lookup_service=_LookupStub(),
    )

    assert workflow.state == MappingWorkflowState.REVIEWING

    workflow.finalize(
        project=project,
        input_hashes={"segments.json": "abc123"},
        model_versions={"mapper": "v1"},
    )

    assert workflow.state == MappingWorkflowState.COMPLETED
    assert project.processing_state == ProcessingState.READY_FOR_UPLOAD


def test_mapping_completion_writes_fr040_checkpoint(tmp_path: Path) -> None:
    project_store = _ProjectStoreStub()
    checkpoint_store = _CheckpointStoreStub()
    workflow = MappingWorkflow(project_store, checkpoint_store, mapper=CompositeMapper())
    project = _make_project(tmp_path)

    mappings = workflow.auto_map(
        project=project,
        segments=[_make_segment(0)],
        entries=[_make_entry(1, "Nocturne")],
        form_responses=[],
        transcription_results=[],
        lookup_service=_LookupStub(),
    )
    checkpoint = workflow.finalize(
        project=project,
        input_hashes={"mappings.json": "hash"},
        model_versions={"mapper": "v1"},
    )

    assert len(mappings) == 1
    assert len(checkpoint_store.saved) == 1
    assert checkpoint.stage == PipelineStage.MAPPING
    assert checkpoint.status == CheckpointStatus.VALID
    assert f"mappings:{len(mappings)}" in checkpoint.output_references


def test_manual_assignment_and_verification_flow(tmp_path: Path) -> None:
    project_store = _ProjectStoreStub()
    checkpoint_store = _CheckpointStoreStub()
    workflow = MappingWorkflow(project_store, checkpoint_store, mapper=CompositeMapper())
    project = _make_project(tmp_path)
    segment = _make_segment(0)
    original_entry = _make_entry(1, "Piece A")
    reassigned_entry = _make_entry(2, "Piece B")
    response = FormResponse(
        id="form-1",
        performer_name="Performer",
        piece_title="Piece B",
        privacy_preference=PrivacySetting.UNLISTED,
    )

    workflow.auto_map(
        project=project,
        segments=[segment],
        entries=[original_entry, reassigned_entry],
        form_responses=[response],
        transcription_results=[],
        lookup_service=_LookupStub(),
    )
    workflow.manual_assign(
        segment_id=str(segment.id),
        program_entry_id=reassigned_entry.id,
        form_response_id=response.id,
    )
    workflow.verify_mapping(segment_id=str(segment.id), verified=True)
    mapping = workflow.get_mapping(str(segment.id))

    assert mapping.program_entry_id == reassigned_entry.id
    assert mapping.form_response_id == response.id
    assert mapping.match_method == MatchMethod.MANUAL
    assert mapping.user_verified is True
    assert project_store.mappings_by_project[str(project.id)][0].program_entry_id == reassigned_entry.id

    checkpoint = workflow.finalize(project=project, input_hashes={"map": "1"}, model_versions={"mapper": "v1"})
    assert asdict(checkpoint)["stage"] == PipelineStage.MAPPING


def test_manual_unassign_resets_derived_metadata(tmp_path: Path) -> None:
    project_store = _ProjectStoreStub()
    checkpoint_store = _CheckpointStoreStub()
    workflow = MappingWorkflow(project_store, checkpoint_store, mapper=CompositeMapper())
    project = _make_project(tmp_path)
    segment = _make_segment(0)
    entry = _make_entry(1, "Title A")

    workflow.auto_map(
        project=project,
        segments=[segment],
        entries=[entry],
        form_responses=[],
        transcription_results=[],
        lookup_service=_LookupStub(),
    )
    workflow.manual_assign(segment_id=str(segment.id), program_entry_id=None, form_response_id=None)
    mapping = workflow.get_mapping(str(segment.id))

    assert mapping.program_entry_id is None
    assert mapping.form_response_id is None
    assert mapping.final_title == ""
    assert mapping.final_description == ""
    assert mapping.final_privacy == PrivacySetting.PUBLIC


def test_manual_assign_rejects_unknown_ids(tmp_path: Path) -> None:
    project_store = _ProjectStoreStub()
    checkpoint_store = _CheckpointStoreStub()
    workflow = MappingWorkflow(project_store, checkpoint_store, mapper=CompositeMapper())
    project = _make_project(tmp_path)
    segment = _make_segment(0)

    workflow.auto_map(
        project=project,
        segments=[segment],
        entries=[_make_entry(1, "Known Piece")],
        form_responses=[],
        transcription_results=[],
        lookup_service=_LookupStub(),
    )

    with pytest.raises(KeyError):
        workflow.manual_assign(segment_id=str(segment.id), program_entry_id="unknown-entry")
