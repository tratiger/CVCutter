from __future__ import annotations

from cvcutter.presentation.flet_app.viewmodel_helpers import localized


class SetupWizardView:
    def heading(self) -> str:
        return localized("setup.title")
