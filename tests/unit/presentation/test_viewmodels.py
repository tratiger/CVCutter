"""Unit tests for presentation view-models (T062)."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, Thread
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from cvcutter.domain.models.project import ProjectConfig
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.models.upload import QuotaState, UploadRecord
from cvcutter.domain.services.types import ProgressEvent
from cvcutter.presentation.viewmodels.load_vm import LoadViewModel
from cvcutter.presentation.viewmodels.preview_vm import PreviewViewModel
from cvcutter.presentation.viewmodels.process_vm import ProcessViewModel
from cvcutter.presentation.viewmodels.settings_vm import SettingsViewModel
from cvcutter.presentation.viewmodels.upload_vm import UploadViewModel
from cvcutter.shared.types import ExportStatus, PrivacySetting, UploadStatus
from tests.conftest import make_project_config, make_segment_dict

if TYPE_CHECKING:
    from pathlib import Path


class MockLoadWorkflow:
    """Mock application service for load workflow operations."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_project(self, **payload: object) -> dict[str, object]:
        self.calls.append(payload)
        return {"project_id": "project-1", **payload}


class MockProcessingWorkflow:
    """Mock application service for processing workflow operations."""

    def __init__(self, *, detection_mode: str = "full", fallback_reason: str | None = None) -> None:
        self.start_calls = 0
        self.resume_calls = 0
        self.pause_calls = 0
        self.cancel_calls = 0
        self._detection_mode = detection_mode
        self._fallback_reason = fallback_reason

    def start(
        self,
        project_id: str,
        progress_callback,
    ) -> list[PerformanceSegment]:
        del project_id
        self.start_calls += 1
        message = "audio-only 検出へフォールバック" if self._detection_mode == "audio_only" else "検出処理を実行中"
        progress_callback(
            ProgressEvent(
                stage="DETECTION",
                current=1,
                total=2,
                message=message,
            ),
        )
        return [_make_segment(detection_mode=self._detection_mode, fallback_reason=self._fallback_reason)]

    def resume(
        self,
        project_id: str,
        progress_callback,
    ) -> list[PerformanceSegment]:
        del project_id
        self.resume_calls += 1
        progress_callback(
            ProgressEvent(
                stage="EXPORT",
                current=1,
                total=1,
                message="エクスポートを再開",
            ),
        )
        return [_make_segment()]

    def pause(self) -> None:
        self.pause_calls += 1

    def cancel(self) -> None:
        self.cancel_calls += 1


class MockPreviewWorkflow:
    """Mock application service for preview/mapping workflow operations."""

    def __init__(self) -> None:
        self.export_calls = 0
        self.auto_map_calls = 0
        self.finalize_calls = 0

    def export_segments(self, project_id: str, segments: list[PerformanceSegment]) -> None:
        del project_id, segments
        self.export_calls += 1

    def auto_map(self, project_id: str) -> None:
        del project_id
        self.auto_map_calls += 1

    def finalize_mappings(self, project_id: str) -> None:
        del project_id
        self.finalize_calls += 1


class MockUploadWorkflow:
    """Mock application service for upload workflow operations."""

    def __init__(self) -> None:
        self.start_calls = 0
        self.pause_calls = 0
        self.retry_calls: list[str] = []
        self._records = [
            _make_upload_record(status=UploadStatus.COMPLETED),
            _make_upload_record(status=UploadStatus.FAILED, error_detail="network"),
        ]
        self._quota = QuotaState(daily_limit=10_000, daily_used=4_800, reset_timestamp_utc=datetime.now(UTC))

    def start_upload(self, project_id: str) -> list[UploadRecord]:
        del project_id
        self.start_calls += 1
        return list(self._records)

    def pause_upload(self) -> None:
        self.pause_calls += 1

    def retry_failed(self, upload_record_id: str) -> UploadRecord:
        self.retry_calls.append(upload_record_id)
        for record in self._records:
            if record.id == upload_record_id:
                record.transition_to(UploadStatus.PENDING)
                record.error_detail = None
                return record
        raise ValueError("unknown upload id")

    def quota_state(self) -> QuotaState:
        return self._quota


class MockSettingsWorkflow:
    """Mock application service for settings operations."""

    def __init__(self) -> None:
        self.saved: list[ProjectConfig] = []
        self.authenticate_calls = 0
        self.connection_calls = 0
        self.retention_calls: list[str] = []
        self.purge_calls: list[str] = []

    def load_config(self) -> ProjectConfig:
        return ProjectConfig(**make_project_config())

    def save_config(self, config: ProjectConfig) -> None:
        self.saved.append(config)

    def authenticate(self) -> bool:
        self.authenticate_calls += 1
        return True

    def test_connection(self) -> bool:
        self.connection_calls += 1
        return True

    def set_artifact_retention(self, policy: str) -> None:
        self.retention_calls.append(policy)

    def purge_artifacts(self, project_id: str) -> None:
        self.purge_calls.append(project_id)


def _make_segment(
    *,
    detection_mode: str = "full",
    fallback_reason: str | None = None,
) -> PerformanceSegment:
    raw = make_segment_dict(detection_mode=detection_mode)
    return PerformanceSegment(
        id=UUID(str(raw["id"])),
        segment_index=int(raw["segment_index"]),
        start_time_seconds=float(raw["start_time_seconds"]),
        end_time_seconds=float(raw["end_time_seconds"]),
        detection_confidence=float(raw["detection_confidence"]),
        effective_detection_mode=str(raw["effective_detection_mode"]),
        detection_signals=[],
        fallback_reason=fallback_reason if fallback_reason is not None else raw["fallback_reason"],
        exported_file_path=None,
        export_status=ExportStatus.NOT_EXPORTED,
        user_adjusted=False,
    )


def _make_upload_record(
    *,
    status: UploadStatus,
    error_detail: str | None = None,
) -> UploadRecord:
    return UploadRecord(
        id=str(uuid4()),
        segment_id=str(uuid4()),
        mapping_id=str(uuid4()),
        upload_status=status,
        privacy_setting=PrivacySetting.PUBLIC,
        error_detail=error_detail,
    )


def test_load_viewmodel_add_remove_reorder_and_validation(tmp_path: Path) -> None:
    workflow = MockLoadWorkflow()
    vm = LoadViewModel(workflow=workflow, output_directory=tmp_path)
    video_a = tmp_path / "a.mp4"
    video_b = tmp_path / "b.mp4"
    video_a.write_bytes(b"a")
    video_b.write_bytes(b"b")

    vm.project_name = "春の演奏会"
    vm.add_videos([video_a, video_b])
    vm.reorder_videos(1, 0)
    vm.remove_video(1)
    vm.validate()

    assert vm.video_files == [video_b]
    assert vm.can_proceed is True
    assert vm.validation_errors == []


def test_load_viewmodel_create_project_uses_workflow(tmp_path: Path) -> None:
    workflow = MockLoadWorkflow()
    vm = LoadViewModel(workflow=workflow, output_directory=tmp_path)
    video_path = tmp_path / "concert.mp4"
    video_path.write_bytes(b"video")
    vm.project_name = "本番"
    vm.add_videos([video_path])

    project = vm.create_project()

    assert project["project_id"] == "project-1"
    assert workflow.calls
    assert workflow.calls[0]["video_files"] == [video_path]


def test_process_viewmodel_start_pause_cancel_and_state_transitions() -> None:
    workflow = MockProcessingWorkflow()
    vm = ProcessViewModel(workflow=workflow)

    vm.start_processing("project-1")
    vm.pause_processing()
    vm.cancel_processing()

    assert workflow.start_calls == 1
    assert workflow.pause_calls == 1
    assert workflow.cancel_calls == 1
    assert vm.current_stage == "検出"
    assert vm.is_processing is False
    assert vm.current_operation == "キャンセルしました。"


def test_process_viewmodel_pause_and_cancel_handle_workflow_errors() -> None:
    class FailingControlWorkflow(MockProcessingWorkflow):
        def pause(self) -> None:
            raise RuntimeError("pause boom")

        def cancel(self) -> None:
            raise RuntimeError("cancel boom")

    vm = ProcessViewModel(workflow=FailingControlWorkflow())
    vm.pause_processing()
    vm.cancel_processing()

    assert len(vm.errors) == 2
    assert vm.current_operation == "キャンセルに失敗しました。"


def test_process_viewmodel_resume_uses_last_started_project_id() -> None:
    class RecordingWorkflow(MockProcessingWorkflow):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, str]] = []

        def start(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
            self.calls.append(("start", project_id))
            return super().start(project_id, progress_callback)

        def resume(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
            self.calls.append(("resume", project_id))
            return super().resume(project_id, progress_callback)

    workflow = RecordingWorkflow()
    vm = ProcessViewModel(workflow=workflow)

    vm.start_processing("project-123")
    vm.resume_processing()

    assert workflow.calls == [("start", "project-123"), ("resume", "project-123")]


@pytest.mark.parametrize("fallback_reason", ["YOLO_DISABLED", "YOLO_RUNTIME_UNAVAILABLE"])
def test_fr012_reduced_accuracy_notice_propagates_for_audio_only_detection(
    fallback_reason: str,
) -> None:
    workflow = MockProcessingWorkflow(detection_mode="audio_only", fallback_reason=fallback_reason)
    vm = ProcessViewModel(workflow=workflow)

    vm.start_processing("project-1")

    assert vm.detection_mode == "audio_only"
    assert vm.reduced_accuracy_notice is not None
    assert "精度" in vm.reduced_accuracy_notice


def test_preview_viewmodel_segment_selection_boundary_adjust_and_mapping_commands() -> None:
    segment = _make_segment()
    workflow = MockPreviewWorkflow()
    vm = PreviewViewModel(workflow=workflow, segments=[segment], project_id="project-1")

    vm.select_segment(str(segment.id))
    vm.adjust_boundary(str(segment.id), 10.0, 80.0)
    vm.assign_mapping(str(segment.id), "program-1")
    vm.assign_form_response(str(segment.id), "form-1")

    assert vm.selected_segment_id == str(segment.id)
    assert segment.start_time_seconds == 10.0
    assert segment.end_time_seconds == 80.0
    assert vm.mappings[str(segment.id)]["program_entry_id"] == "program-1"
    assert vm.mappings[str(segment.id)]["form_response_id"] == "form-1"


def test_preview_viewmodel_split_updates_selection_and_segment_order() -> None:
    first = _make_segment()
    second = _make_segment()
    second.segment_index = 1
    workflow = MockPreviewWorkflow()
    vm = PreviewViewModel(workflow=workflow, segments=[first, second], project_id="project-1")
    vm.select_segment(str(first.id))

    left, _ = vm.split_segment(str(first.id), 60.0)

    assert vm.selected_segment_id == str(left.id)
    assert [segment.segment_index for segment in vm.segments] == [0, 1, 2]


def test_preview_viewmodel_mapping_commands_require_existing_segment() -> None:
    segment = _make_segment()
    workflow = MockPreviewWorkflow()
    vm = PreviewViewModel(workflow=workflow, segments=[segment], project_id="project-1")

    with pytest.raises(ValueError):
        vm.assign_mapping("missing", "program-1")


def test_upload_viewmodel_start_upload_retry_failed_and_quota_display() -> None:
    workflow = MockUploadWorkflow()
    vm = UploadViewModel(workflow=workflow, project_id="project-1")

    vm.start_upload()
    failed_record = next(record for record in vm.upload_records if record.upload_status == UploadStatus.FAILED)
    vm.retry_failed(failed_record.id)

    retried = next(record for record in vm.upload_records if record.id == failed_record.id)
    assert workflow.start_calls == 1
    assert workflow.retry_calls == [failed_record.id]
    assert retried.upload_status == UploadStatus.PENDING
    assert "残り" in vm.quota_display


def test_upload_viewmodel_pause_upload_alias() -> None:
    workflow = MockUploadWorkflow()
    vm = UploadViewModel(workflow=workflow, project_id="project-1")
    vm.is_uploading = True

    vm.pause_upload()

    assert vm.is_uploading is False
    assert workflow.pause_calls == 1


def test_upload_viewmodel_pause_handles_workflow_errors() -> None:
    class FailingUploadWorkflow(MockUploadWorkflow):
        def pause_upload(self) -> None:
            raise RuntimeError("pause boom")

    vm = UploadViewModel(workflow=FailingUploadWorkflow(), project_id="project-1")
    vm.is_uploading = True

    vm.pause_upload()

    assert vm.errors
    assert vm.current_operation == "アップロード一時停止に失敗しました。"
    assert vm.is_uploading is True


def test_settings_viewmodel_update_config_and_authenticate_commands() -> None:
    workflow = MockSettingsWorkflow()
    vm = SettingsViewModel(workflow=workflow)

    vm.update_config("enable_yolo_detection", False)
    auth_ok = vm.authenticate()
    connection_ok = vm.test_connection()
    vm.set_artifact_retention("auto-clean")
    vm.purge_artifacts("project-1")

    assert vm.config.enable_yolo_detection is False
    assert workflow.saved
    assert auth_ok is True and connection_ok is True
    assert workflow.authenticate_calls == 1
    assert workflow.connection_calls == 1
    assert workflow.retention_calls == ["auto-clean"]
    assert workflow.purge_calls == ["project-1"]


def test_settings_viewmodel_rejects_invalid_config_values_without_raising() -> None:
    workflow = MockSettingsWorkflow()
    vm = SettingsViewModel(workflow=workflow)
    before = vm.config.video_audio_volume if vm.config is not None else 0.6

    vm.update_config("video_audio_volume", 99.0)

    assert vm.config.video_audio_volume == before
    assert vm.errors
    assert vm.status_message == "設定値が不正です。"


def test_settings_viewmodel_falls_back_to_default_when_load_fails() -> None:
    class FailingSettingsWorkflow(MockSettingsWorkflow):
        def load_config(self) -> ProjectConfig:
            raise OSError("broken config")

    vm = SettingsViewModel(workflow=FailingSettingsWorkflow())

    assert isinstance(vm.config, ProjectConfig)
    assert "初期設定" in vm.status_message


def test_preview_viewmodel_reduced_accuracy_notice_from_audio_only_segments() -> None:
    audio_only_segment = _make_segment(detection_mode="audio_only", fallback_reason="YOLO_DISABLED")
    workflow = MockPreviewWorkflow()
    vm = PreviewViewModel(workflow=workflow, segments=[audio_only_segment], project_id="project-1")

    vm.refresh_notice_from_segments()

    assert vm.detection_mode == "audio_only"
    assert vm.reduced_accuracy_notice is not None


def test_process_viewmodel_clears_audio_only_notice_when_processing_fails() -> None:
    class FailingWorkflow(MockProcessingWorkflow):
        def start(
            self,
            project_id: str,
            progress_callback,
        ) -> list[PerformanceSegment]:
            del project_id
            progress_callback(
                ProgressEvent(
                    stage="DETECTION",
                    current=1,
                    total=2,
                    message="audio-only 検出へフォールバック",
                ),
            )
            raise RuntimeError("boom")

    vm = ProcessViewModel(workflow=FailingWorkflow())

    vm.start_processing("project-1")

    assert vm.errors
    assert vm.detection_mode == "full"
    assert vm.reduced_accuracy_notice is None


def test_process_viewmodel_failed_rerun_clears_previous_segments() -> None:
    class FlakyWorkflow(MockProcessingWorkflow):
        def __init__(self) -> None:
            super().__init__()
            self.should_fail = False

        def start(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
            if self.should_fail:
                raise RuntimeError("boom")
            return super().start(project_id, progress_callback)

    workflow = FlakyWorkflow()
    vm = ProcessViewModel(workflow=workflow)

    vm.start_processing("project-1")
    assert vm.detected_segments

    workflow.should_fail = True
    vm.start_processing("project-1")

    assert vm.errors
    assert vm.detected_segments == []


def test_process_viewmodel_cancel_state_not_overwritten_by_background_completion() -> None:
    class BlockingWorkflow(MockProcessingWorkflow):
        def __init__(self) -> None:
            super().__init__()
            self._cancel_gate = Event()

        def start(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
            del project_id
            progress_callback(ProgressEvent(stage="DETECTION", current=1, total=2, message="検出中"))
            self._cancel_gate.wait(timeout=1.0)
            return []

        def cancel(self) -> None:
            super().cancel()
            self._cancel_gate.set()

    workflow = BlockingWorkflow()
    vm = ProcessViewModel(workflow=workflow)
    worker = Thread(target=vm.start_processing, args=("project-1",))
    worker.start()

    vm.cancel_processing()
    worker.join(timeout=1.0)

    assert vm.current_operation == "キャンセルしました。"


def test_process_viewmodel_rejected_concurrent_start_does_not_overwrite_project_id() -> None:
    class SlowWorkflow(MockProcessingWorkflow):
        def __init__(self) -> None:
            super().__init__()
            self._gate = Event()
            self.start_projects: list[str] = []

        def start(self, project_id: str, progress_callback) -> list[PerformanceSegment]:
            self.start_projects.append(project_id)
            progress_callback(ProgressEvent(stage="DETECTION", current=1, total=2, message="検出中"))
            self._gate.wait(timeout=1.0)
            return []

    workflow = SlowWorkflow()
    vm = ProcessViewModel(workflow=workflow)
    worker = Thread(target=vm.start_processing, args=("project-A",))
    worker.start()

    vm.start_processing("project-B")
    workflow._gate.set()
    worker.join(timeout=1.0)

    assert workflow.start_projects == ["project-A"]
    assert vm.project_id == "project-A"


def test_upload_viewmodel_retry_failed_handles_unknown_record_without_raising() -> None:
    workflow = MockUploadWorkflow()
    vm = UploadViewModel(workflow=workflow, project_id="project-1")
    vm.start_upload()

    vm.retry_failed("unknown-id")

    assert vm.errors
    assert vm.current_operation == "再試行に失敗しました。"


def test_upload_viewmodel_reports_quota_refresh_failure_after_successful_upload() -> None:
    class QuotaFailWorkflow(MockUploadWorkflow):
        def quota_state(self) -> QuotaState:
            raise RuntimeError("quota boom")

    vm = UploadViewModel(workflow=QuotaFailWorkflow(), project_id="project-1")
    vm.start_upload()

    assert vm.upload_records
    assert vm.current_operation == "アップロードは完了しましたがクォータ取得に失敗しました。"
    assert vm.errors


def test_upload_viewmodel_retry_handles_quota_refresh_failure() -> None:
    class RetryQuotaFailWorkflow(MockUploadWorkflow):
        def __init__(self) -> None:
            super().__init__()
            self.fail_quota = False

        def quota_state(self) -> QuotaState:
            if self.fail_quota:
                raise RuntimeError("quota down")
            return super().quota_state()

    workflow = RetryQuotaFailWorkflow()
    vm = UploadViewModel(workflow=workflow, project_id="project-1")
    vm.start_upload()
    workflow.fail_quota = True
    failed_record = next(record for record in vm.upload_records if record.upload_status == UploadStatus.FAILED)

    vm.retry_failed(failed_record.id)

    assert vm.errors
    assert vm.current_operation == "再試行は完了しましたがクォータ取得に失敗しました。"


def test_settings_viewmodel_handles_command_failures_without_raising() -> None:
    class FailingCommandsWorkflow(MockSettingsWorkflow):
        def save_config(self, config: ProjectConfig) -> None:
            del config
            raise OSError("disk full")

        def authenticate(self) -> bool:
            raise RuntimeError("auth boom")

        def test_connection(self) -> bool:
            raise RuntimeError("conn boom")

        def set_artifact_retention(self, policy: str) -> None:
            del policy
            raise RuntimeError("retention boom")

        def purge_artifacts(self, project_id: str) -> None:
            del project_id
            raise RuntimeError("purge boom")

    vm = SettingsViewModel(workflow=FailingCommandsWorkflow())
    before = vm.config.enable_yolo_detection if vm.config is not None else True

    vm.update_config("enable_yolo_detection", not before)
    auth_ok = vm.authenticate()
    conn_ok = vm.test_connection()
    vm.set_artifact_retention("retain")
    vm.purge_artifacts("project-1")

    assert auth_ok is False
    assert conn_ok is False
    assert vm.config.enable_yolo_detection == before
    assert len(vm.errors) == 5


def test_settings_viewmodel_reset_to_defaults_handles_save_failure() -> None:
    class ResetFailWorkflow(MockSettingsWorkflow):
        def save_config(self, config: ProjectConfig) -> None:
            del config
            raise OSError("disk full")

    vm = SettingsViewModel(workflow=ResetFailWorkflow())
    vm.config = ProjectConfig(**make_project_config(enable_yolo_detection=False))
    previous = vm.config

    vm.reset_to_defaults()

    assert vm.config == previous
    assert vm.errors
    assert vm.status_message == "設定の初期化に失敗しました。"
