"""Flet application shell for CVCutter."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

import flet as ft

from cvcutter.application.checkpoint_manager import CheckpointManager
from cvcutter.application.pipeline import PipelineOrchestrator
from cvcutter.domain.models.project import ConcertProject, ExternalAudio, ProjectConfig, SourceVideo
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.models.upload import QuotaState, UploadRecord
from cvcutter.infrastructure.ffmpeg.transcoder import FFmpegTranscoder
from cvcutter.infrastructure.persistence.json_checkpoint_store import JsonCheckpointStore
from cvcutter.infrastructure.persistence.json_config import JsonConfig
from cvcutter.infrastructure.persistence.json_project_store import JsonProjectStore
from cvcutter.presentation.viewmodels.load_vm import LoadViewModel
from cvcutter.presentation.viewmodels.preview_vm import PreviewViewModel
from cvcutter.presentation.viewmodels.process_vm import ProcessViewModel
from cvcutter.presentation.viewmodels.settings_vm import SettingsViewModel
from cvcutter.presentation.viewmodels.upload_vm import UploadViewModel
from cvcutter.presentation.views.load_view import build_load_view
from cvcutter.presentation.views.preview_view import build_preview_view
from cvcutter.presentation.views.process_view import build_process_view
from cvcutter.presentation.views.settings_view import build_settings_view
from cvcutter.presentation.views.upload_view import build_upload_view
from cvcutter.shared.hashing import compute_file_hash
from cvcutter.shared.types import PrivacySetting, ProcessingState, UploadStatus


@dataclass
class _AppState:
    """Transient UI session state."""

    project_id: str = "active-project"


class _VideoProbeResult(Protocol):
    @property
    def duration_seconds(self) -> float:
        ...

    @property
    def resolution(self) -> tuple[int, int]:
        ...

    @property
    def codec(self) -> str:
        ...

    @property
    def file_size_bytes(self) -> int:
        ...


class _VideoProber(Protocol):
    def probe(self, file_path: Path) -> _VideoProbeResult:
        ...


class _PipelineWorkflow(Protocol):
    def run(self, project: ConcertProject, progress_callback) -> ConcertProject:
        ...

    def resume(self, project: ConcertProject, progress_callback) -> ConcertProject:
        ...

    def restart(self, project: ConcertProject, progress_callback) -> ConcertProject:
        ...

    def pause(self) -> None:
        ...

    def cancel(self) -> None:
        ...


def _default_base_dir() -> Path:
    """Resolve the per-user persistent storage directory."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "cvcutter"
    return Path.home() / "AppData" / "Local" / "cvcutter"


class _LoadWorkflowService:
    """Persist newly created projects from load-screen inputs."""

    def __init__(
        self,
        state: _AppState,
        *,
        project_store: JsonProjectStore,
        video_io: _VideoProber,
        config_store: JsonConfig,
    ) -> None:
        self._state = state
        self._project_store = project_store
        self._video_io = video_io
        self._config_store = config_store
        self.last_payload: dict[str, object] | None = None

    def create_project(
        self,
        *,
        project_name: str,
        video_files: list[Path],
        external_audio_file: Path | None,
        program_pdf_file: Path | None,
        form_csv_file: Path | None,
        form_remote_id: str | None,
        form_remote_sheet_id: str | None,
        output_directory: Path,
    ) -> dict[str, object]:
        if not video_files:
            raise ValueError("動画ファイルを1つ以上選択してください。")

        resolved_videos = [Path(path).expanduser().resolve() for path in video_files]
        for source_path in resolved_videos:
            if not source_path.exists():
                raise ValueError(f"動画ファイルが見つかりません: {source_path}")

        resolved_output_dir = Path(output_directory).expanduser().resolve()
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        config = self._config_store.load_config()
        now_utc = datetime.now(UTC)

        source_videos: list[SourceVideo] = []
        for order_index, source_path in enumerate(resolved_videos):
            probe = self._video_io.probe(source_path)
            width, height = probe.resolution
            if width <= 0 or height <= 0:
                width, height = 1, 1
            source_videos.append(
                SourceVideo(
                    id=str(uuid4()),
                    file_path=source_path,
                    order_index=order_index,
                    duration_seconds=max(0.0, probe.duration_seconds),
                    resolution=(width, height),
                    codec=(probe.codec or "unknown").strip() or "unknown",
                    creation_timestamp=datetime.fromtimestamp(source_path.stat().st_mtime, tz=UTC),
                    file_hash=compute_file_hash(source_path),
                    file_size_bytes=max(int(probe.file_size_bytes), source_path.stat().st_size),
                ),
            )

        resolved_program_pdf = Path(program_pdf_file).expanduser().resolve() if program_pdf_file else None
        if resolved_program_pdf is not None and not resolved_program_pdf.exists():
            raise ValueError(f"プログラムPDFが見つかりません: {resolved_program_pdf}")

        resolved_form_csv = Path(form_csv_file).expanduser().resolve() if form_csv_file else None
        if resolved_form_csv is not None and not resolved_form_csv.exists():
            raise ValueError(f"フォームCSVが見つかりません: {resolved_form_csv}")

        external_audio = self._build_external_audio(external_audio_file, config.audio_sync_sample_rate)

        project = ConcertProject(
            id=uuid4(),
            name=project_name.strip(),
            event_date=None,
            venue=None,
            source_videos=source_videos,
            external_audio=external_audio,
            program_pdf_path=resolved_program_pdf,
            form_source_path=resolved_form_csv,
            form_remote_id=form_remote_id,
            form_remote_sheet_id=form_remote_sheet_id,
            output_directory=resolved_output_dir,
            config_snapshot=config,
            processing_state=ProcessingState.CREATED,
            created_at=now_utc,
            updated_at=now_utc,
        )
        self._project_store.save_project(project)
        if self._project_store.load_project(str(project.id)) is None:
            raise RuntimeError("プロジェクト情報の保存に失敗しました。保存先の権限を確認してください。")

        self._state.project_id = str(project.id)
        payload: dict[str, object] = {
            "project_name": project_name,
            "video_files": video_files,
            "external_audio_file": external_audio_file,
            "program_pdf_file": program_pdf_file,
            "form_csv_file": form_csv_file,
            "form_remote_id": form_remote_id,
            "form_remote_sheet_id": form_remote_sheet_id,
            "output_directory": output_directory,
        }
        self.last_payload = dict(payload)
        return {"project_id": self._state.project_id, **payload}

    def _build_external_audio(
        self,
        external_audio_file: Path | None,
        sample_rate: int,
    ) -> ExternalAudio | None:
        if external_audio_file is None:
            return None
        audio_path = Path(external_audio_file).expanduser().resolve()
        if not audio_path.exists():
            raise ValueError(f"外部音声ファイルが見つかりません: {audio_path}")
        probe = self._video_io.probe(audio_path)
        audio_format = audio_path.suffix.strip(".").lower() or "wav"
        return ExternalAudio(
            id=str(uuid4()),
            file_path=audio_path,
            duration_seconds=max(0.0, probe.duration_seconds),
            format=audio_format,
            sample_rate=max(1, int(sample_rate)),
            file_hash=compute_file_hash(audio_path),
        )


class _ProcessingWorkflowService:
    """Processing workflow adapter backed by the real pipeline orchestrator."""

    def __init__(
        self,
        *,
        project_store: JsonProjectStore,
        pipeline: _PipelineWorkflow,
    ) -> None:
        self._project_store = project_store
        self._pipeline = pipeline

    def start(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
        project = self._require_project(project_id)
        self._pipeline.restart(project, progress_callback)
        return self._project_store.load_segments(project_id)

    def resume(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
        project = self._require_project(project_id)
        self._pipeline.resume(project, progress_callback)
        return self._project_store.load_segments(project_id)

    def pause(self) -> None:
        self._pipeline.pause()

    def cancel(self) -> None:
        self._pipeline.cancel()

    def _require_project(self, project_id: str) -> ConcertProject:
        project = self._project_store.load_project(project_id)
        if project is None:
            raise ValueError(f"プロジェクトが見つかりません: {project_id}")
        return project


class _PreviewWorkflowService:
    """In-memory preview workflow stub."""

    def export_segments(self, project_id: str, segments: list[PerformanceSegment]) -> None:
        del project_id, segments

    def auto_map(self, project_id: str) -> None:
        del project_id

    def finalize_mappings(self, project_id: str) -> None:
        del project_id


class _UploadWorkflowService:
    """In-memory upload workflow stub."""

    def __init__(self) -> None:
        self._quota = QuotaState(
            daily_limit=10_000,
            daily_used=0,
            reset_timestamp_utc=datetime.now(UTC),
        )
        self._records = [
            UploadRecord(
                id="00000000-0000-0000-0000-000000000101",
                segment_id="00000000-0000-0000-0000-000000000201",
                mapping_id="00000000-0000-0000-0000-000000000301",
                upload_status=UploadStatus.PENDING,
                privacy_setting=PrivacySetting.PUBLIC,
            ),
        ]

    def start_upload(self, project_id: str) -> list[UploadRecord]:
        del project_id
        for record in self._records:
            if record.upload_status == UploadStatus.PENDING:
                record.transition_to(UploadStatus.UPLOADING)
                record.youtube_video_id = "dummy001"
                record.youtube_url = "https://www.youtube.com/watch?v=dummy001"
                record.transition_to(UploadStatus.COMPLETED)
                self._quota = self._quota.record_upload(record.quota_cost)
        return list(self._records)

    def pause_upload(self) -> None:
        return

    def retry_failed(self, upload_record_id: str) -> UploadRecord:
        for record in self._records:
            if record.id == upload_record_id:
                record.transition_to(UploadStatus.PENDING)
                record.error_detail = None
                return record
        raise ValueError("指定されたアップロードIDが存在しません。")

    def quota_state(self) -> QuotaState:
        return self._quota


class _SettingsWorkflowService:
    """Settings workflow backed by persistent configuration storage."""

    def __init__(self, config_store: JsonConfig | None = None) -> None:
        self._config_store = config_store
        self._config = self._config_store.load_config() if self._config_store is not None else ProjectConfig()
        self._artifact_policy = "auto-clean"
        self._last_purged: str | None = None

    def load_config(self) -> ProjectConfig:
        if self._config_store is not None:
            self._config = self._config_store.load_config()
        return ProjectConfig(**asdict(self._config))

    def save_config(self, config: ProjectConfig) -> None:
        self._config = config
        if self._config_store is not None:
            self._config_store.save_config(config)

    def authenticate(self) -> bool:
        return True

    def test_connection(self) -> bool:
        return True

    def set_artifact_retention(self, policy: str) -> None:
        self._artifact_policy = policy

    def purge_artifacts(self, project_id: str) -> None:
        self._last_purged = project_id


def launch() -> None:
    """Launch the Flet desktop application."""
    ft.app(target=_build_page, view=ft.AppView.FLET_APP)


def _build_page(page: ft.Page) -> None:
    """Create the app shell with five-step workflow navigation."""
    page.title = "CVCutter"
    page.theme_mode = ft.ThemeMode.DARK
    if page.window is not None:
        page.window.width = 1100
        page.window.height = 800
    page.padding = 16

    base_dir = _default_base_dir()
    project_store = JsonProjectStore(base_dir)
    checkpoint_store = JsonCheckpointStore(base_dir)
    checkpoint_manager = CheckpointManager(checkpoint_store)
    video_io = FFmpegTranscoder()
    config_store = JsonConfig(base_dir)
    pipeline = PipelineOrchestrator(
        video_io=video_io,
        checkpoint_manager=checkpoint_manager,
        project_store=project_store,
    )

    app_state = _AppState()
    settings_workflow = _SettingsWorkflowService(config_store=config_store)
    settings_vm = SettingsViewModel(workflow=settings_workflow)
    load_workflow = _LoadWorkflowService(
        app_state,
        project_store=project_store,
        video_io=video_io,
        config_store=config_store,
    )
    load_vm = LoadViewModel(workflow=load_workflow, output_directory=base_dir / "output")
    process_vm = ProcessViewModel(
        workflow=_ProcessingWorkflowService(
            project_store=project_store,
            pipeline=pipeline,
        ),
    )
    preview_vm = PreviewViewModel(
        workflow=_PreviewWorkflowService(),
        project_id=app_state.project_id,
        segments=[],
    )
    upload_vm = UploadViewModel(workflow=_UploadWorkflowService(), project_id=app_state.project_id)
    load_picker = ft.FilePicker()
    page.services.append(load_picker)

    body = ft.Container(expand=True)
    last_preview_signature: tuple[tuple[object, ...], ...] | None = None

    def sync_preview_segments() -> None:
        nonlocal last_preview_signature
        if not process_vm.detected_segments:
            if last_preview_signature is not None:
                preview_vm.replace_segments([])
                last_preview_signature = None
            return
        signature = tuple(
            (
                summary.segment_id,
                summary.segment_index,
                summary.start_time_seconds,
                summary.end_time_seconds,
                summary.effective_detection_mode,
                summary.fallback_reason,
                summary.detection_confidence,
                summary.exported_file_path,
                summary.export_status.value,
            )
            for summary in process_vm.detected_segments
        )
        if signature == last_preview_signature:
            return
        converted_segments = [
            PerformanceSegment(
                id=UUID(summary.segment_id),
                segment_index=summary.segment_index,
                start_time_seconds=summary.start_time_seconds,
                end_time_seconds=summary.end_time_seconds,
                detection_confidence=summary.detection_confidence,
                effective_detection_mode=summary.effective_detection_mode,
                detection_signals=[],
                fallback_reason=summary.fallback_reason,
                exported_file_path=Path(summary.exported_file_path)
                if summary.exported_file_path is not None
                else None,
                export_status=summary.export_status,
                user_adjusted=False,
            )
            for summary in process_vm.detected_segments
        ]
        preview_vm.replace_segments(converted_segments)
        last_preview_signature = signature

    def render(index: int) -> None:
        process_vm.project_id = app_state.project_id
        preview_vm.project_id = app_state.project_id
        upload_vm.project_id = app_state.project_id
        settings_vm.active_project_id = app_state.project_id
        if index == 0:
            body.content = build_load_view(load_vm, page, load_picker)
        elif index == 1:
            body.content = build_process_view(process_vm, page)
        elif index == 2:
            sync_preview_segments()
            body.content = build_preview_view(preview_vm, page)
        elif index == 3:
            body.content = build_upload_view(upload_vm, page)
        else:
            body.content = build_settings_view(settings_vm, page)
        page.update()

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=120,
        min_extended_width=180,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.FOLDER_OPEN,
                selected_icon=ft.Icons.FOLDER_OPEN,
                label="ファイル読み込み",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.MOVIE_FILTER,
                selected_icon=ft.Icons.MOVIE_FILTER,
                label="動画処理",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.PREVIEW,
                selected_icon=ft.Icons.PREVIEW,
                label="プレビュー&紐付け",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.CLOUD_UPLOAD,
                selected_icon=ft.Icons.CLOUD_UPLOAD,
                label="アップロード",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS,
                selected_icon=ft.Icons.SETTINGS,
                label="設定",
            ),
        ],
        on_change=lambda event: render(event.control.selected_index or 0),
    )
    page.add(
        ft.Row(
            controls=[
                rail,
                ft.VerticalDivider(width=1),
                body,
            ],
            expand=True,
        ),
    )
    render(0)
