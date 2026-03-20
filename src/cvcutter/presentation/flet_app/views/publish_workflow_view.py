from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from cvcutter.presentation.flet_app.viewmodel_helpers import localized
from cvcutter.presentation.flet_app.viewmodels.publish_workflow_viewmodel import PublishWorkflowViewModel


@dataclass(slots=True)
class PublishWorkflowView:
    viewmodel: PublishWorkflowViewModel

    def build_controls(self) -> list[ft.Control]:
        return [
            ft.Text(localized("publish.title"), size=20),
            ft.Switch(label="Allow plaintext credentials", value=self.viewmodel.consent_given),
            ft.Text(f"Credentials path: {self.viewmodel.credentials_path}"),
            ft.Text(
                "Plaintext storage enabled" if self.viewmodel.can_save_plaintext_credentials() else "Consent required",
            ),
        ]

    def summary(self) -> dict[str, object]:
        return {
            "title": localized("publish.title"),
            "consent_given": self.viewmodel.consent_given,
            "can_save_plaintext_credentials": self.viewmodel.can_save_plaintext_credentials(),
            "credentials_path": str(self.viewmodel.credentials_path),
        }
