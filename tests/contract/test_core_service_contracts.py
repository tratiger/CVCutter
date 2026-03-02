"""Service-contract conformance tests for core persistence ports (T009)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest

from cvcutter.domain.models.checkpoint import Checkpoint
from cvcutter.domain.models.metadata import (
    FormResponse,
    MatchSignal,
    ProgramEntry,
    VideoMetadataMapping,
)
from cvcutter.domain.models.project import ConcertProject, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.models.upload import QuotaState, UploadRecord
from cvcutter.domain.services.checkpoint_store import CheckpointStore
from cvcutter.domain.services.credential_store import CredentialStore
from cvcutter.domain.services.project_store import ProjectStore
from cvcutter.domain.services.quota_state_store import QuotaStateStore
from cvcutter.infrastructure.persistence.json_checkpoint_store import JsonCheckpointStore
from cvcutter.infrastructure.persistence.json_project_store import JsonProjectStore
from cvcutter.infrastructure.persistence.json_quota_state_store import JsonQuotaStateStore
from cvcutter.shared.types import (
    CheckpointStatus,
    ExportStatus,
    MatchMethod,
    MatchSignalType,
    PipelineStage,
    PrivacySetting,
    ProcessingState,
    UploadStatus,
)
from tests.conftest import (
    make_checkpoint_dict,
    make_project_config,
    make_project_id,
    make_segment_dict,
    make_upload_record_dict,
)

if TYPE_CHECKING:
    from pathlib import Path

try:
    from cvcutter.infrastructure.persistence.json_credential_store import JsonCredentialStore
except ImportError as exc:
    JsonCredentialStore = None  # type: ignore[assignment]
    JSON_CREDENTIAL_STORE_IMPORT_ERROR: Exception | None = exc
else:
    JSON_CREDENTIAL_STORE_IMPORT_ERROR = None


def _require_adapter(
    adapter: type[Any] | None,
    *,
    import_error: Exception | None,
    adapter_name: str,
) -> type[Any]:
    if adapter is None:
        message = f"{adapter_name} is not available yet."
        if import_error is not None:
            message = f"{message} Import error: {import_error!r}"
        pytest.fail(message)
    return adapter


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _make_project(base_dir: Path, *, project_id: str | None = None, name: str = "contract-project") -> ConcertProject:
    source_path = base_dir / "source.mp4"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"\x00" * 16)

    output_dir = base_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    source_video = SourceVideo(
        id=make_project_id(),
        file_path=source_path,
        order_index=0,
        duration_seconds=120.0,
        resolution=(1920, 1080),
        codec="h264",
        creation_timestamp=now,
        file_hash="abc123",
        file_size_bytes=source_path.stat().st_size,
    )

    return ConcertProject(
        id=UUID(project_id or make_project_id()),
        name=name,
        event_date=None,
        venue="main-hall",
        source_videos=[source_video],
        external_audio=None,
        program_pdf_path=None,
        form_source_path=None,
        form_remote_id=None,
        form_remote_sheet_id=None,
        output_directory=output_dir,
        config_snapshot=ProjectConfig(**make_project_config()),
        processing_state=ProcessingState.CREATED,
        created_at=now,
        updated_at=now,
    )


def _make_segment() -> PerformanceSegment:
    raw = make_segment_dict()
    fallback_reason = _optional_str(raw.get("fallback_reason"))
    return PerformanceSegment(
        id=UUID(str(raw["id"])),
        segment_index=int(raw["segment_index"]),
        start_time_seconds=float(raw["start_time_seconds"]),
        end_time_seconds=float(raw["end_time_seconds"]),
        detection_confidence=float(raw["detection_confidence"]),
        effective_detection_mode=str(raw["effective_detection_mode"]),
        detection_signals=[],
        fallback_reason=fallback_reason,
        exported_file_path=None,
        export_status=ExportStatus(str(raw["export_status"])),
        user_adjusted=bool(raw["user_adjusted"]),
    )


def _make_program_entry() -> ProgramEntry:
    return ProgramEntry(
        id=str(uuid4()),
        order_number=1,
        piece_title="Symphony No.5",
        composer="Beethoven",
        performer_names=["Performer A"],
        ensemble="School Orchestra",
        instrument="Piano",
        raw_text="Program entry raw text",
    )


def _make_form_response() -> FormResponse:
    return FormResponse(
        id=str(uuid4()),
        performer_name="Performer A",
        piece_title="Symphony No.5",
        privacy_preference=PrivacySetting.PUBLIC,
        display_name_override=None,
        custom_description=None,
        raw_data={"performer_name": "Performer A"},
    )


def _make_mapping(
    *,
    segment_id: str,
    program_entry_id: str,
    form_response_id: str,
) -> VideoMetadataMapping:
    return VideoMetadataMapping(
        id=uuid4(),
        segment_id=segment_id,
        program_entry_id=program_entry_id,
        form_response_id=form_response_id,
        match_confidence=0.95,
        match_method=MatchMethod.SEQUENTIAL,
        match_signals=[
            MatchSignal(
                signal_type=MatchSignalType.SEQUENTIAL_ORDER,
                confidence=0.95,
                evidence="ordered-by-program",
            ),
        ],
        user_verified=True,
        final_title="Symphony No.5 - Performer A",
        final_description="Contract test upload metadata.",
        final_privacy=PrivacySetting.PUBLIC,
        final_category_id="10",
        final_tags=["concert", "classical"],
    )


def _make_upload(*, segment_id: str, mapping_id: str) -> UploadRecord:
    raw = make_upload_record_dict(segment_id=segment_id, mapping_id=mapping_id, status="PENDING")
    return UploadRecord(
        id=str(raw["id"]),
        segment_id=str(raw["segment_id"]),
        mapping_id=str(raw["mapping_id"]),
        youtube_video_id=_optional_str(raw.get("youtube_video_id")),
        upload_status=UploadStatus(str(raw["upload_status"])),
        privacy_setting=PrivacySetting(str(raw["privacy_setting"])),
        playlist_id=_optional_str(raw.get("playlist_id")),
        quota_cost=int(raw["quota_cost"]),
        retry_count=int(raw["retry_count"]),
        error_detail=_optional_str(raw.get("error_detail")),
        resumable_upload_uri=_optional_str(raw.get("resumable_upload_uri")),
        bytes_uploaded=int(raw["bytes_uploaded"]),
        failure_kind=_optional_str(raw.get("failure_kind")),
        session_invalidated_at_utc=None,
        restart_from_zero=bool(raw["restart_from_zero"]),
        youtube_url=_optional_str(raw.get("youtube_url")),
        uploaded_at=None,
    )


def _make_checkpoint(project_id: str, *, stage: PipelineStage = PipelineStage.DETECTION) -> Checkpoint:
    raw = make_checkpoint_dict(
        project_id=project_id,
        stage=stage.value,
        status=CheckpointStatus.VALID.value,
        config_snapshot=make_project_config(),
    )
    input_hashes_raw = raw.get("input_hashes")
    input_hashes = (
        {str(key): str(value) for key, value in input_hashes_raw.items()}
        if isinstance(input_hashes_raw, dict)
        else {}
    )
    config_snapshot_raw = raw.get("config_snapshot")
    config_snapshot = dict(config_snapshot_raw) if isinstance(config_snapshot_raw, dict) else {}
    model_versions_raw = raw.get("model_versions")
    model_versions = (
        {str(key): str(value) for key, value in model_versions_raw.items()}
        if isinstance(model_versions_raw, dict)
        else {}
    )
    output_references_raw = raw.get("output_references")
    output_references = [str(item) for item in output_references_raw] if isinstance(
        output_references_raw, list
    ) else []
    segment_index_raw = raw.get("segment_index")
    segment_index = segment_index_raw if isinstance(segment_index_raw, int) else None

    return Checkpoint(
        id=UUID(str(raw["id"])),
        project_id=str(raw["project_id"]),
        stage=PipelineStage(str(raw["stage"])),
        status=CheckpointStatus(str(raw["status"])),
        created_at=datetime.fromisoformat(str(raw["created_at"])),
        input_hashes=input_hashes,
        config_snapshot=config_snapshot,
        model_versions=model_versions,
        output_references=output_references,
        segment_index=segment_index,
        error_detail=_optional_str(raw.get("error_detail")),
    )


@pytest.mark.contract
def test_json_project_store_satisfies_project_store_protocol(tmp_path: Path) -> None:
    store = JsonProjectStore(tmp_path)
    assert isinstance(store, ProjectStore)


@pytest.mark.contract
def test_json_checkpoint_store_satisfies_checkpoint_store_protocol(tmp_path: Path) -> None:
    store = JsonCheckpointStore(tmp_path)
    assert isinstance(store, CheckpointStore)


@pytest.mark.contract
def test_json_quota_state_store_satisfies_quota_state_store_protocol(tmp_path: Path) -> None:
    store = JsonQuotaStateStore(tmp_path)
    assert isinstance(store, QuotaStateStore)


@pytest.mark.contract
def test_json_credential_store_satisfies_credential_store_protocol(tmp_path: Path) -> None:
    store_cls = _require_adapter(
        JsonCredentialStore,
        import_error=JSON_CREDENTIAL_STORE_IMPORT_ERROR,
        adapter_name="JsonCredentialStore",
    )
    store = store_cls(tmp_path)
    assert isinstance(store, CredentialStore)


@pytest.mark.contract
def test_json_project_store_round_trip_and_missing_behavior(tmp_path: Path) -> None:
    store = JsonProjectStore(tmp_path)
    project_id = make_project_id()
    missing_project_id = make_project_id()

    project = _make_project(tmp_path, project_id=project_id, name="initial-name")
    segment = _make_segment()
    program_entry = _make_program_entry()
    form_response = _make_form_response()
    mapping = _make_mapping(
        segment_id=str(segment.id),
        program_entry_id=program_entry.id,
        form_response_id=form_response.id,
    )
    upload = _make_upload(segment_id=str(segment.id), mapping_id=str(mapping.id))

    store.save_project(project)
    store.save_segments(project_id, [segment])
    store.save_mappings(project_id, [mapping])
    store.save_upload_records(project_id, [upload])
    store.save_program_entries(project_id, [program_entry])
    store.save_form_responses(project_id, [form_response])

    loaded_project = store.load_project(project_id)
    assert loaded_project is not None
    assert loaded_project.id == project.id
    assert loaded_project.name == "initial-name"
    assert len(store.load_segments(project_id)) == 1
    assert len(store.load_mappings(project_id)) == 1
    assert len(store.load_upload_records(project_id)) == 1
    assert len(store.load_program_entries(project_id)) == 1
    assert len(store.load_form_responses(project_id)) == 1

    assert store.load_project(missing_project_id) is None
    assert store.load_segments(missing_project_id) == []
    assert store.load_mappings(missing_project_id) == []
    assert store.load_upload_records(missing_project_id) == []
    assert store.load_program_entries(missing_project_id) == []
    assert store.load_form_responses(missing_project_id) == []


@pytest.mark.contract
def test_json_checkpoint_store_round_trip_and_missing_behavior(tmp_path: Path) -> None:
    store = JsonCheckpointStore(tmp_path)
    project_id = make_project_id()

    checkpoint = _make_checkpoint(project_id, stage=PipelineStage.DETECTION)
    store.save(checkpoint)

    loaded = store.load(project_id, PipelineStage.DETECTION)
    assert loaded is not None
    assert loaded.id == checkpoint.id
    assert loaded.status == CheckpointStatus.VALID
    assert [item.id for item in store.load_all(project_id)] == [checkpoint.id]

    missing_project_id = make_project_id()
    assert store.load(missing_project_id, PipelineStage.DETECTION) is None
    assert store.load_all(missing_project_id) == []


@pytest.mark.contract
def test_json_quota_state_store_round_trip_and_missing_behavior(tmp_path: Path) -> None:
    store = JsonQuotaStateStore(tmp_path)
    assert store.load() is None

    now = datetime.now(UTC)
    quota_state = QuotaState(
        daily_limit=10_000,
        daily_used=1_600,
        reset_timestamp_utc=now,
        last_updated=now,
    )
    store.save(quota_state)

    loaded = store.load()
    assert loaded is not None
    assert loaded.daily_limit == quota_state.daily_limit
    assert loaded.daily_used == quota_state.daily_used


@pytest.mark.contract
def test_json_credential_store_round_trip_and_missing_behavior(tmp_path: Path) -> None:
    store_cls = _require_adapter(
        JsonCredentialStore,
        import_error=JSON_CREDENTIAL_STORE_IMPORT_ERROR,
        adapter_name="JsonCredentialStore",
    )
    store = store_cls(tmp_path)

    service_name = "youtube"
    credentials = {"access_token": "token-1", "refresh_token": "token-2"}
    store.save(service_name, credentials)

    loaded = store.load(service_name)
    assert loaded == credentials

    missing = "missing-service"
    assert store.load(missing) is None
    assert store.redacted_summary(missing) == {}


@pytest.mark.contract
def test_json_project_store_basic_concurrent_access_safety(tmp_path: Path) -> None:
    writer = JsonProjectStore(tmp_path)
    reader = JsonProjectStore(tmp_path)
    project_id = make_project_id()

    writer.save_project(_make_project(tmp_path, project_id=project_id, name="writer-version"))
    first_read = reader.load_project(project_id)
    assert first_read is not None
    assert first_read.name == "writer-version"

    reader.save_project(_make_project(tmp_path, project_id=project_id, name="reader-version"))
    second_read = writer.load_project(project_id)
    assert second_read is not None
    assert second_read.name == "reader-version"


@pytest.mark.contract
def test_json_checkpoint_store_basic_concurrent_access_safety(tmp_path: Path) -> None:
    writer = JsonCheckpointStore(tmp_path)
    reader = JsonCheckpointStore(tmp_path)
    project_id = make_project_id()

    first = _make_checkpoint(project_id, stage=PipelineStage.DETECTION)
    writer.save(first)
    loaded_first = reader.load(project_id, PipelineStage.DETECTION)
    assert loaded_first is not None
    assert loaded_first.id == first.id

    second = _make_checkpoint(project_id, stage=PipelineStage.DETECTION)
    reader.save(second)
    loaded_second = writer.load(project_id, PipelineStage.DETECTION)
    assert loaded_second is not None
    assert loaded_second.id == second.id


@pytest.mark.contract
def test_json_quota_state_store_basic_concurrent_access_safety(tmp_path: Path) -> None:
    writer = JsonQuotaStateStore(tmp_path)
    reader = JsonQuotaStateStore(tmp_path)
    now = datetime.now(UTC)

    first = QuotaState(
        daily_limit=10_000,
        daily_used=1_600,
        reset_timestamp_utc=now,
        last_updated=now,
    )
    writer.save(first)
    loaded_first = reader.load()
    assert loaded_first is not None
    assert loaded_first.daily_used == 1_600

    second = QuotaState(
        daily_limit=10_000,
        daily_used=3_200,
        reset_timestamp_utc=now,
        last_updated=now,
    )
    reader.save(second)
    loaded_second = writer.load()
    assert loaded_second is not None
    assert loaded_second.daily_used == 3_200


@pytest.mark.contract
def test_json_credential_store_basic_concurrent_access_safety(tmp_path: Path) -> None:
    store_cls = _require_adapter(
        JsonCredentialStore,
        import_error=JSON_CREDENTIAL_STORE_IMPORT_ERROR,
        adapter_name="JsonCredentialStore",
    )
    writer = store_cls(tmp_path)
    reader = store_cls(tmp_path)
    service_name = "youtube"

    writer.save(service_name, {"access_token": "token-a"})
    assert reader.load(service_name) == {"access_token": "token-a"}

    reader.save(service_name, {"access_token": "token-b"})
    assert writer.load(service_name) == {"access_token": "token-b"}
