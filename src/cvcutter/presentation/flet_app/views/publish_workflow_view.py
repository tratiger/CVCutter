from __future__ import annotations

from dataclasses import dataclass

from cvcutter.presentation.flet_app.viewmodel_helpers import localized
from cvcutter.presentation.flet_app.viewmodels.publish_workflow_viewmodel import PublishWorkflowViewModel


@dataclass(slots=True)
class PublishWorkflowView:
    viewmodel: PublishWorkflowViewModel

    def summary(self) -> dict[str, object]:
        return {
            "title": localized("publish.title"),
            "consent_given": self.viewmodel.consent_given,
            "can_save_plaintext_credentials": self.viewmodel.can_save_plaintext_credentials(),
            "credentials_path": str(self.viewmodel.credentials_path),
        }
