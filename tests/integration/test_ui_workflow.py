"""Integration scaffold for Flet UI workflow (T063)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import flet as ft
import pytest

from cvcutter.domain.models.project import ProjectConfig
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.presentation.viewmodels.preview_vm import PreviewViewModel
from cvcutter.presentation.viewmodels.settings_vm import SettingsViewModel
from cvcutter.presentation.viewmodels.upload_vm import UploadViewModel
from cvcutter.presentation.views.preview_view import build_preview_view
from cvcutter.presentation.views.settings_view import build_settings_view
from cvcutter.presentation.views.upload_view import build_upload_view
from cvcutter.shared.types import ExportStatus
from tests.conftest import make_project_config, make_segment_dict

if TYPE_CHECKING:
    from cvcutter.domain.models.upload import QuotaState, UploadRecord

pytestmark = pytest.mark.integration


class _MockPreviewWorkflow:
    """Minimal preview workflow stub."""

    def export_segments(self, project_id: str, segments: list[PerformanceSegment]) -> None:
        del project_id, segments

    def auto_map(self, project_id: str) -> None:
        del project_id

    def finalize_mappings(self, project_id: str) -> None:
        del project_id


class _MockSettingsWorkflow:
    def __init__(self) -> None:
        self.purge_calls: list[str] = []

    def load_config(self) -> ProjectConfig:
        return ProjectConfig(**make_project_config())

    def save_config(self, config: ProjectConfig) -> None:
        del config

    def authenticate(self) -> bool:
        return True

    def test_connection(self) -> bool:
        return True

    def set_artifact_retention(self, policy: str) -> None:
        del policy

    def purge_artifacts(self, project_id: str) -> None:
        self.purge_calls.append(project_id)


class _QuotaFailUploadWorkflow:
    def start_upload(self, project_id: str) -> list[UploadRecord]:
        del project_id
        return []

    def pause_upload(self) -> None:
        return

    def retry_failed(self, upload_record_id: str) -> UploadRecord:
        raise ValueError(upload_record_id)

    def quota_state(self) -> QuotaState:
        raise RuntimeError("quota down")


def _make_segment() -> PerformanceSegment:
    raw = make_segment_dict()
    return PerformanceSegment(
        id=UUID(str(raw["id"])),
        segment_index=int(raw["segment_index"]),
        start_time_seconds=float(raw["start_time_seconds"]),
        end_time_seconds=float(raw["end_time_seconds"]),
        detection_confidence=float(raw["detection_confidence"]),
        effective_detection_mode=str(raw["effective_detection_mode"]),
        detection_signals=[],
        fallback_reason=None,
        exported_file_path=None,
        export_status=ExportStatus.NOT_EXPORTED,
        user_adjusted=False,
    )


def test_preview_layout_scaffold_for_fr063_side_by_side_panel() -> None:
    vm = PreviewViewModel(workflow=_MockPreviewWorkflow(), segments=[_make_segment()], project_id="project-1")

    control = build_preview_view(vm)

    assert isinstance(control, ft.Column)
    layout_row = next((item for item in control.controls if isinstance(item, ft.Row)), None)
    assert layout_row is not None
    assert len(layout_row.controls) >= 3
    # Placeholder: add strict widget-tree assertions for thumbnail/timecode/metadata controls.


def test_settings_purge_uses_active_project_id() -> None:
    workflow = _MockSettingsWorkflow()
    vm = SettingsViewModel(workflow=workflow, active_project_id="project-xyz")
    view = build_settings_view(vm)

    purge_row = next(
        control
        for control in view.controls
        if isinstance(control, ft.Row)
        and any(getattr(button, "content", "") == "成果物を削除" for button in control.controls)
    )
    purge_button = next(
        button for button in purge_row.controls if getattr(button, "content", "") == "成果物を削除"
    )
    purge_button.on_click(None)

    assert workflow.purge_calls == ["project-xyz"]


def test_upload_view_handles_quota_refresh_failure_without_crashing() -> None:
    vm = UploadViewModel(workflow=_QuotaFailUploadWorkflow(), project_id="project-1")

    control = build_upload_view(vm)

    assert isinstance(control, ft.Column)
    assert vm.current_operation == "クォータ情報の取得に失敗しました。"
