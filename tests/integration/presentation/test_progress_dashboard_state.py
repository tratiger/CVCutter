from cvcutter.presentation.flet_app.viewmodels.progress_dashboard_viewmodel import ProgressDashboardViewModel
from cvcutter.presentation.flet_app.viewmodel_helpers import localized


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
