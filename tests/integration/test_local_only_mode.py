"""Integration checks for local-only workflows with cloud services disabled (T110)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import MethodType
from uuid import uuid4

import pytest

from cvcutter.application.checkpoint_manager import CheckpointManager
from cvcutter.application.mapping_workflow import MappingWorkflow
from cvcutter.application.pipeline import PipelineOrchestrator
from cvcutter.application.upload_workflow import UploadWorkflow
from cvcutter.domain.mapping import CompositeMapper
from cvcutter.domain.models.metadata import FormResponse, ProgramEntry, VideoMetadataMapping
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.models.upload import QuotaState, UploadRecord
from cvcutter.domain.services.types import DiskSpaceInfo, UploadResult
from cvcutter.infrastructure.persistence.json_checkpoint_store import JsonCheckpointStore
from cvcutter.infrastructure.persistence.json_project_store import JsonProjectStore
from cvcutter.infrastructure.persistence.json_quota_state_store import JsonQuotaStateStore
from cvcutter.shared.types import (
    ExportStatus,
    MatchMethod,
    PipelineStage,
    PrivacySetting,
    ProcessingState,
    UploadStatus,
)

pytestmark = pytest.mark.integration


class _LocalVideoIO:
    def concatenate(self, video_paths, output_path, progress_callback=None):
        del video_paths
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\x01" * 8192)
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
        output_path.write_bytes(b"\x02" * 4096)
        if progress_callback is not None:
            progress_callback(1, 1)
        return output_path

    def check_gpu_available(self):
        return False

    def get_disk_space(self, path):
        return DiskSpaceInfo(total_bytes=20_000_000, free_bytes=19_000_000, path=path)


class _LookupUnavailable:
    def lookup(self, title: str, composer: str | None = None, performers: list[str] | None = None):
        del title, composer, performers
        return []

    def is_available(self) -> bool:
        return False

    def dictionary_revision(self) -> str:
        return "unavailable"


class _MappingCheckpointStore:
    def __init__(self) -> None:
        self.saved = []

    def save(self, checkpoint) -> None:
        self.saved.append(checkpoint)


class _DisabledUploadService:
    def authenticate(self) -> bool:
        return False

    def upload(
        self,
        file_path,
        metadata,
        progress_callback=None,
        resumable_uri=None,
        bytes_uploaded=0,
        session_callback=None,
    ) -> UploadResult:
        del file_path, metadata, progress_callback, resumable_uri, bytes_uploaded, session_callback
        raise AssertionError("upload must not be called when authentication is disabled")

    def create_playlist(self, title: str, description: str = "", privacy=PrivacySetting.PUBLIC) -> str:
        del title, description, privacy
        raise AssertionError("playlist creation must not run when authentication is disabled")

    def add_to_playlist(self, playlist_id: str, video_id: str) -> None:
        del playlist_id, video_id
        raise AssertionError("playlist insertion must not run when authentication is disabled")


class _UploadCheckpointManager:
    def __init__(self) -> None:
        self.saved = []

    def save_checkpoint(self, checkpoint) -> None:
        self.saved.append(checkpoint)


@pytest.fixture
def local_context(tmp_path):
    app_data = tmp_path / "appdata"
    now = datetime.now(UTC)
    source_path = tmp_path / "concert.mp4"
    source_path.write_bytes(b"\x00" * 40_000)
    project = ConcertProject(
        id=uuid4(),
        name="local_only_project",
        event_date=None,
        venue="hall",
        source_videos=[
            SourceVideo(
                id=str(uuid4()),
                file_path=source_path,
                order_index=0,
                duration_seconds=180.0,
                resolution=(1920, 1080),
                codec="h264",
                creation_timestamp=now,
                file_hash="source-hash",
                file_size_bytes=source_path.stat().st_size,
            ),
        ],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=tmp_path / "exports",
        config_snapshot=ProjectConfig(enable_gemini=False),
        processing_state=ProcessingState.CREATED,
        created_at=now,
        updated_at=now,
    )
    project_store = JsonProjectStore(app_data)
    checkpoint_store = JsonCheckpointStore(app_data)
    checkpoint_manager = CheckpointManager(checkpoint_store)
    project_store.save_project(project)

    orchestrator = PipelineOrchestrator(
        video_io=_LocalVideoIO(),
        checkpoint_manager=checkpoint_manager,
        project_store=project_store,
    )

    def _stub_detection(self, project_value, concatenated_path, progress_callback):
        del progress_callback
        segment = PerformanceSegment(
            id=uuid4(),
            segment_index=0,
            start_time_seconds=0.0,
            end_time_seconds=60.0,
            detection_confidence=0.9,
            effective_detection_mode="full",
            detection_signals=[],
        )
        self._project_store.save_segments(str(project_value.id), [segment])
        self._save_checkpoint(
            project=project_value,
            stage=PipelineStage.DETECTION,
            input_hashes=self._hash_for_concatenated_stage(concatenated_path),
            model_versions=self._model_versions(PipelineStage.DETECTION),
            output_references=["segments:1"],
        )
        return [segment]

    orchestrator._run_detection = MethodType(_stub_detection, orchestrator)
    return project, project_store, orchestrator, app_data


def _build_program_entry() -> ProgramEntry:
    return ProgramEntry(
        id="entry-1",
        order_number=1,
        piece_title="Symphony No. 5",
        composer="Beethoven",
        performer_names=["Performer A"],
        ensemble=None,
        instrument=None,
        raw_text="Symphony No. 5",
    )


def test_full_local_only_operation_with_external_services_disabled(local_context) -> None:
    project, project_store, orchestrator, _ = local_context
    orchestrator.run(project)
    segments = project_store.load_segments(str(project.id))
    mapping_checkpoint_store = _MappingCheckpointStore()
    mapping_workflow = MappingWorkflow(
        project_store=project_store,
        checkpoint_store=mapping_checkpoint_store,
        mapper=CompositeMapper(),
    )

    mappings = mapping_workflow.auto_map(
        project=project,
        segments=segments,
        entries=[_build_program_entry()],
        form_responses=[],
        transcription_results=[],
        lookup_service=_LookupUnavailable(),
    )
    checkpoint = mapping_workflow.finalize(
        project=project,
        input_hashes={"segments.json": "hash"},
        model_versions={"mapper": "local-only"},
    )

    assert project.config_snapshot.enable_gemini is False
    assert project.processing_state == ProcessingState.READY_FOR_UPLOAD
    assert checkpoint.stage == PipelineStage.MAPPING
    assert mappings
    assert all(segment.exported_file_path and segment.exported_file_path.exists() for segment in segments)


def test_gemini_disabled_does_not_block_mapping(local_context) -> None:
    project, project_store, _, _ = local_context
    project.processing_state = ProcessingState.MAPPING
    segment = PerformanceSegment(
        id=uuid4(),
        segment_index=0,
        start_time_seconds=0.0,
        end_time_seconds=45.0,
        detection_confidence=0.85,
        effective_detection_mode="full",
        detection_signals=[],
        export_status=ExportStatus.EXPORTED,
    )
    project_store.save_segments(str(project.id), [segment])
    mapping_checkpoint_store = _MappingCheckpointStore()
    mapping_workflow = MappingWorkflow(project_store, mapping_checkpoint_store, mapper=CompositeMapper())

    mappings = mapping_workflow.auto_map(
        project=project,
        segments=[segment],
        entries=[_build_program_entry()],
        form_responses=[
            FormResponse(
                id="form-1",
                performer_name="Performer A",
                piece_title="Symphony No. 5",
                privacy_preference=PrivacySetting.UNLISTED,
            ),
        ],
        transcription_results=[],
        lookup_service=_LookupUnavailable(),
    )
    mapping_workflow.finalize(
        project=project,
        input_hashes={"mapping.json": "hash"},
        model_versions={"mapper": "local-only"},
    )

    assert project.config_snapshot.enable_gemini is False
    assert project.processing_state == ProcessingState.READY_FOR_UPLOAD
    assert len(mappings) == 1
    assert mappings[0].match_method in {MatchMethod.SEQUENTIAL, MatchMethod.FORM}


def test_youtube_disabled_does_not_block_processing(local_context) -> None:
    project, project_store, orchestrator, app_data = local_context
    orchestrator.run(project)
    segments = project_store.load_segments(str(project.id))
    segment = segments[0]
    mapping = VideoMetadataMapping(
        id=uuid4(),
        segment_id=str(segment.id),
        program_entry_id="entry-1",
        form_response_id=None,
        match_confidence=1.0,
        match_method=MatchMethod.MANUAL,
        match_signals=[],
        user_verified=True,
        final_title="Symphony No. 5 - Performer A",
        final_description="Local-only mapping result",
        final_privacy=PrivacySetting.PUBLIC,
        final_category_id="10",
        final_tags=["concert"],
    )
    upload_record = UploadRecord(
        id=str(uuid4()),
        segment_id=str(segment.id),
        mapping_id=str(mapping.id),
        upload_status=UploadStatus.PENDING,
        privacy_setting=PrivacySetting.PUBLIC,
    )
    project_store.save_mappings(str(project.id), [mapping])
    project_store.save_upload_records(str(project.id), [upload_record])

    quota_store = JsonQuotaStateStore(app_data)
    quota_store.save(
        QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC) + timedelta(hours=12),
            last_updated=datetime.now(UTC),
        ),
    )
    upload_workflow = UploadWorkflow(
        upload_service=_DisabledUploadService(),
        quota_state_store=quota_store,
        project_store=project_store,
        checkpoint_manager=_UploadCheckpointManager(),
    )
    result = upload_workflow.start_upload(project, [upload_record])

    assert result[0].upload_status == UploadStatus.QUEUED
    assert result[0].failure_kind == "AUTH_FAILURE"
    assert result[0].error_detail == "Authentication failed; queued for retry."
    assert project.processing_state == ProcessingState.MAPPING
    assert segment.exported_file_path is not None and segment.exported_file_path.exists()
