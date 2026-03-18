from __future__ import annotations

from pathlib import Path

from cvcutter.presentation.flet_app.viewmodels.publish_workflow_viewmodel import PublishWorkflowViewModel
from cvcutter.presentation.flet_app.views.publish_workflow_view import PublishWorkflowView


def test_publish_workflow_view_exposes_consent_and_storage_summary(tmp_path: Path) -> None:
    vm = PublishWorkflowViewModel(
        consent_given=False,
        credentials_path=tmp_path / "plaintext-credentials.json",
    )
    summary = PublishWorkflowView(vm).summary()

    assert summary["title"] == "公開"
    assert summary["consent_given"] is False
    assert summary["can_save_plaintext_credentials"] is False
    assert str(summary["credentials_path"]).endswith("plaintext-credentials.json")
