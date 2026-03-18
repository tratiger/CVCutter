from __future__ import annotations

from cvcutter.presentation.flet_app.viewmodels.progress_dashboard_viewmodel import ProgressDashboardViewModel
from cvcutter.presentation.flet_app.views.progress_dashboard_view import ProgressDashboardView


def test_progress_dashboard_view_builds_operator_summary() -> None:
    vm = ProgressDashboardViewModel()
    vm.record_stage_update("ingest", "completed")
    vm.record_stage_update("classify", "running")
    view = ProgressDashboardView(vm)

    summary = view.summary()
    assert summary["title"] == "進捗"
    assert summary["current_stage"] == "classify"
    assert summary["completed_stages"] == ["ingest"]
