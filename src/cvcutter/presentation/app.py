"""Flet application shell for CVCutter."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import flet as ft

from cvcutter.domain.models.project import ProjectConfig
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.models.upload import QuotaState, UploadRecord
from cvcutter.domain.services.types import ProgressEvent
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
from cvcutter.shared.types import ExportStatus, PrivacySetting, UploadStatus


@dataclass
class _AppState:
    """Transient UI session state."""

    project_id: str = "active-project"


class _LoadWorkflowService:
    """In-memory load workflow stub."""

    def __init__(self, state: _AppState) -> None:
        self._state = state
        self.last_payload: dict[str, object] | None = None

    def create_project(self, **payload: object) -> dict[str, object]:
        self._state.project_id = str(uuid4())
        self.last_payload = dict(payload)
        return {"project_id": self._state.project_id, **payload}


class _ProcessingWorkflowService:
    """In-memory processing workflow stub."""

    def __init__(self, yolo_enabled_provider) -> None:
        self._yolo_enabled_provider = yolo_enabled_provider
        self._pause_requested = False
        self._cancel_requested = False

    def start(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
        return self._run(project_id, progress_callback)

    def resume(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
        return self._run(project_id, progress_callback)

    def pause(self) -> None:
        self._pause_requested = True

    def cancel(self) -> None:
        self._cancel_requested = True

    def _run(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
        del project_id
        self._pause_requested = False
        self._cancel_requested = False
        stage_names = ["CONCATENATION", "DETECTION", "AUDIO_SYNC", "EXPORT", "MAPPING", "UPLOAD"]
        for index, stage_name in enumerate(stage_names, start=1):
            if self._cancel_requested:
                break
            progress_callback(
                ProgressEvent(
                    stage=stage_name,
                    current=index,
                    total=len(stage_names),
                    message=f"{stage_name} を実行中",
                ),
            )
            if self._pause_requested:
                break

        detection_mode = "full" if self._yolo_enabled_provider() else "audio_only"
        fallback_reason = None if detection_mode == "full" else "TOGGLE_DISABLED"
        return [
            PerformanceSegment(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                segment_index=0,
                start_time_seconds=0.0,
                end_time_seconds=120.0,
                detection_confidence=0.82,
                effective_detection_mode=detection_mode,
                detection_signals=[],
                fallback_reason=fallback_reason,
                exported_file_path=None,
                export_status=ExportStatus.NOT_EXPORTED,
                user_adjusted=False,
            ),
        ]


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
    """In-memory settings workflow stub."""

    def __init__(self) -> None:
        self._config = ProjectConfig()
        self._artifact_policy = "auto-clean"
        self._last_purged: str | None = None

    def load_config(self) -> ProjectConfig:
        return ProjectConfig(**asdict(self._config))

    def save_config(self, config: ProjectConfig) -> None:
        self._config = config

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
    ft.app(target=_build_page)


def _build_page(page: ft.Page) -> None:
    """Create the app shell with five-step workflow navigation."""
    page.title = "CVCutter"
    page.theme_mode = ft.ThemeMode.DARK
    if page.window is not None:
        page.window.width = 1100
        page.window.height = 800
    page.padding = 16

    app_state = _AppState()
    settings_workflow = _SettingsWorkflowService()
    settings_vm = SettingsViewModel(workflow=settings_workflow)
    load_workflow = _LoadWorkflowService(app_state)
    load_vm = LoadViewModel(workflow=load_workflow, output_directory=Path.cwd() / "output")
    process_vm = ProcessViewModel(
        workflow=_ProcessingWorkflowService(
            yolo_enabled_provider=lambda: settings_vm.config.enable_yolo_detection
            if settings_vm.config is not None
            else True,
        ),
    )
    preview_vm = PreviewViewModel(
        workflow=_PreviewWorkflowService(),
        project_id=app_state.project_id,
        segments=[],
    )
    upload_vm = UploadViewModel(workflow=_UploadWorkflowService(), project_id=app_state.project_id)
    load_picker = ft.FilePicker()
    page.overlay.append(load_picker)

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
                exported_file_path=None,
                export_status=ExportStatus.NOT_EXPORTED,
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
