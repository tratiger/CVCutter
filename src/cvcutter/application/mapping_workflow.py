"""Application workflow for segment-to-metadata mapping orchestration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from cvcutter.domain.mapping import CompositeMapper
from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.domain.models.metadata import (
    FormResponse,
    MatchSignal,
    ProgramEntry,
    VideoMetadataMapping,
)
from cvcutter.shared.types import (
    CheckpointStatus,
    MatchMethod,
    MatchSignalType,
    PipelineStage,
    PrivacySetting,
    ProcessingState,
)

if TYPE_CHECKING:
    from cvcutter.domain.models.project import ConcertProject
    from cvcutter.domain.models.segment import PerformanceSegment
    from cvcutter.domain.services.checkpoint_store import CheckpointStore
    from cvcutter.domain.services.music_lookup import MusicLookupService
    from cvcutter.domain.services.project_store import ProjectStore
    from cvcutter.domain.services.types import TranscriptionResult


class MappingWorkflowState(StrEnum):
    """State machine for mapping workflow lifecycle."""

    IDLE = "IDLE"
    AUTO_MAPPING = "AUTO_MAPPING"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"


class MappingWorkflow:
    """Coordinate auto mapping, manual corrections, verification, and checkpoint persistence."""

    def __init__(
        self,
        project_store: ProjectStore,
        checkpoint_store: CheckpointStore,
        *,
        mapper: CompositeMapper | None = None,
        mapper_version: str = "composite-mapper:v1",
    ) -> None:
        self._project_store = project_store
        self._checkpoint_store = checkpoint_store
        self._mapper = mapper or CompositeMapper()
        self._mapper_version = mapper_version
        self._state = MappingWorkflowState.IDLE
        self._mappings_by_segment: dict[str, VideoMetadataMapping] = {}
        self._entries_by_id: dict[str, ProgramEntry] = {}
        self._responses_by_id: dict[str, FormResponse] = {}
        self._active_project_id: str | None = None

    @property
    def state(self) -> MappingWorkflowState:
        return self._state

    def auto_map(
        self,
        *,
        project: ConcertProject,
        segments: list[PerformanceSegment],
        entries: list[ProgramEntry],
        form_responses: list[FormResponse],
        transcription_results: list[TranscriptionResult] | dict[str, TranscriptionResult] | None,
        lookup_service: MusicLookupService,
    ) -> list[VideoMetadataMapping]:
        previous_state = self._state
        self._state = MappingWorkflowState.AUTO_MAPPING
        try:
            mappings = self._mapper.map_segments(
                segments=segments,
                entries=entries,
                form_responses=form_responses,
                transcription_results=transcription_results,
                lookup_service=lookup_service,
            )
            project_id = str(project.id)
            self._project_store.save_mappings(project_id, mappings)
            self._mappings_by_segment = {mapping.segment_id: mapping for mapping in mappings}
            self._entries_by_id = {entry.id: entry for entry in entries}
            self._responses_by_id = {response.id: response for response in form_responses}
            self._active_project_id = project_id
            self._state = MappingWorkflowState.REVIEWING
            return self.get_mappings()
        except Exception:
            self._state = previous_state
            raise

    def manual_assign(
        self,
        *,
        segment_id: str,
        program_entry_id: str | None,
        form_response_id: str | None = None,
    ) -> VideoMetadataMapping:
        if program_entry_id is not None and program_entry_id not in self._entries_by_id:
            raise KeyError(f"Unknown program_entry_id={program_entry_id}")
        if form_response_id is not None and form_response_id not in self._responses_by_id:
            raise KeyError(f"Unknown form_response_id={form_response_id}")

        mapping = self.get_mapping(segment_id)
        mapping.program_entry_id = program_entry_id
        mapping.form_response_id = form_response_id
        mapping.match_method = MatchMethod.MANUAL
        mapping.match_confidence = 1.0
        mapping.user_verified = True
        mapping.match_signals = [
            MatchSignal(
                signal_type=MatchSignalType.SEQUENTIAL_ORDER,
                confidence=1.0,
                evidence=f"manual:{program_entry_id or 'unmatched'}",
            ),
        ]
        selected_entry = self._entries_by_id.get(program_entry_id) if program_entry_id is not None else None
        selected_response = (
            self._responses_by_id.get(form_response_id) if form_response_id is not None else None
        )
        mapping.final_title = ""
        mapping.final_description = ""
        mapping.final_privacy = PrivacySetting.PUBLIC
        if selected_entry is not None:
            mapping.final_title = _build_title(selected_entry, selected_response)
            mapping.final_description = _build_description(selected_entry, selected_response)
        elif selected_response is not None:
            mapping.final_title = selected_response.piece_title
            mapping.final_description = selected_response.custom_description or ""
        if selected_response is not None:
            mapping.final_privacy = selected_response.privacy_preference
        self._persist_current_mappings()
        return mapping

    def verify_mapping(self, *, segment_id: str, verified: bool = True) -> VideoMetadataMapping:
        mapping = self.get_mapping(segment_id)
        mapping.user_verified = verified
        self._persist_current_mappings()
        return mapping

    def get_mapping(self, segment_id: str) -> VideoMetadataMapping:
        if segment_id not in self._mappings_by_segment:
            raise KeyError(f"No mapping found for segment_id={segment_id}")
        return self._mappings_by_segment[segment_id]

    def get_mappings(self) -> list[VideoMetadataMapping]:
        return sorted(self._mappings_by_segment.values(), key=lambda mapping: mapping.segment_id)

    def finalize(
        self,
        *,
        project: ConcertProject,
        input_hashes: dict[str, str] | None = None,
        model_versions: dict[str, str] | None = None,
    ) -> Checkpoint:
        mappings = self.get_mappings()
        project_id = str(project.id)
        self._project_store.save_mappings(project_id, mappings)

        checkpoint = Checkpoint(
            id=uuid4(),
            project_id=project_id,
            stage=PipelineStage.MAPPING,
            status=CheckpointStatus.VALID,
            created_at=datetime.now(UTC),
            input_hashes=input_hashes or {"mapping_inputs": "unknown"},
            config_snapshot=asdict(project.config_snapshot),
            model_versions=model_versions or {"mapping_workflow": self._mapper_version},
            output_references=[
                f"mappings:{len(mappings)}",
                *(f"mapping_id:{mapping.id}" for mapping in mappings),
            ],
        )
        self._checkpoint_store.save(checkpoint)

        if project.processing_state == ProcessingState.MAPPING:
            project.transition_to(ProcessingState.READY_FOR_UPLOAD)
            if hasattr(self._project_store, "save_project"):
                self._project_store.save_project(project)  # type: ignore[call-arg]

        self._state = MappingWorkflowState.COMPLETED
        return checkpoint

    def _persist_current_mappings(self) -> None:
        if self._active_project_id is None:
            return
        self._project_store.save_mappings(self._active_project_id, self.get_mappings())


def _build_title(entry: ProgramEntry, response: FormResponse | None) -> str:
    performer_name = ""
    if response is not None and response.display_name_override:
        performer_name = response.display_name_override.strip()
    elif entry.performer_names:
        performer_name = entry.performer_names[0]
    if performer_name:
        return f"{entry.piece_title} - {performer_name}"
    return entry.piece_title


def _build_description(entry: ProgramEntry, response: FormResponse | None) -> str:
    parts: list[str] = []
    if entry.composer:
        parts.append(f"Composer: {entry.composer}")
    if entry.performer_names:
        parts.append(f"Performer: {', '.join(entry.performer_names)}")
    if response is not None and response.custom_description:
        parts.append(response.custom_description.strip())
    return "\n".join(part for part in parts if part)
