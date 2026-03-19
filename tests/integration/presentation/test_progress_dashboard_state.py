from cvcutter.presentation.flet_app.viewmodels.progress_dashboard_viewmodel import ProgressDashboardViewModel
from cvcutter.presentation.flet_app.viewmodel_helpers import localized
from cvcutter.presentation.flet_app.views.progress_dashboard_view import ProgressDashboardView


def test_progress_timeline_and_localization() -> None:
    vm = ProgressDashboardViewModel()
    vm.record_stage_update("ingest", "completed")
    vm.record_stage_update("classify", "running")
    vm.record_stage_update("segment_detect", "failed", error_summary="model unavailable")
    assert vm.current_stage == "segment_detect"
    assert vm.completed_stages == ["ingest"]
    assert "classify" in vm.pending_stages
    assert vm.last_error_summary == "model unavailable"
    assert localized("progress.title") == "進捗"


def test_progress_dashboard_view_provides_next_action_label() -> None:
    vm = ProgressDashboardViewModel()
    vm.record_stage_update("ingest", "completed")
    vm.record_stage_update("classify", "running")
    summary = ProgressDashboardView(vm).summary()
    assert summary["next_action"] == "次のステージ: segment_detect"
