from cvcutter.presentation.flet_app.viewmodels.progress_dashboard_viewmodel import ProgressDashboardViewModel
from cvcutter.presentation.flet_app.viewmodel_helpers import localized


def test_progress_timeline_and_localization() -> None:
    vm = ProgressDashboardViewModel()
    vm.add_event("job.started")
    assert vm.timeline == ["job.started"]
    assert localized("progress.title") == "進捗"
