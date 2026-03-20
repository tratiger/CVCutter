from __future__ import annotations

import flet as ft

from cvcutter.presentation.flet_app.viewmodels.progress_dashboard_viewmodel import ProgressDashboardViewModel
from cvcutter.presentation.flet_app.viewmodels.publish_workflow_viewmodel import PublishWorkflowViewModel
from cvcutter.presentation.flet_app.viewmodels.setup_wizard_viewmodel import SetupWizardViewModel
from cvcutter.presentation.flet_app.views.progress_dashboard_view import ProgressDashboardView
from cvcutter.presentation.flet_app.views.publish_workflow_view import PublishWorkflowView
from cvcutter.presentation.flet_app.views.setup_wizard_view import SetupWizardView



def test_setup_wizard_view_build_controls_returns_flet_controls() -> None:
    vm = SetupWizardViewModel(
        source_path="concert.mp4",
        output_path="out",
        metadata_path="meta.json",
        classification_strategy="content_based",
    )
    controls = SetupWizardView(vm).build_controls()

    assert controls
    assert all(isinstance(control, ft.Control) for control in controls)
    assert any(isinstance(control, ft.TextField) and control.label == "Source" for control in controls)



def test_progress_dashboard_view_build_controls_contains_stage_list() -> None:
    vm = ProgressDashboardViewModel()
    vm.record_stage_update("ingest", "completed")
    view = ProgressDashboardView(vm)

    controls = view.build_controls()

    assert controls
    assert all(isinstance(control, ft.Control) for control in controls)
    assert any(isinstance(control, ft.Column) for control in controls)



def test_publish_workflow_view_build_controls_contains_consent_switch(tmp_path) -> None:
    vm = PublishWorkflowViewModel(
        consent_given=True,
        credentials_path=tmp_path / "plaintext-credentials.json",
    )
    controls = PublishWorkflowView(vm).build_controls()

    assert controls
    assert all(isinstance(control, ft.Control) for control in controls)
    assert any(isinstance(control, ft.Switch) and control.label == "Allow plaintext credentials" for control in controls)
