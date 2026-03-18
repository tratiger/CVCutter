from __future__ import annotations

import os

import flet as ft

from cvcutter.presentation.flet_app.viewmodels.onboarding_flow_viewmodel import OnboardingFlowViewModel


class OnboardingView:
    def __init__(self, viewmodel: OnboardingFlowViewModel | None = None) -> None:
        self._viewmodel = viewmodel or OnboardingFlowViewModel()

    def first_draft_hint(self) -> str:
        return self._viewmodel.current_state

    def preview_progression(self, job_name: str) -> list[str]:
        flow = OnboardingFlowViewModel()
        return [
            flow.current_state,
            flow.create_draft(job_name),
            flow.go_next(),
        ]

    def run(self, *, force_headless: bool | None = None) -> str:
        if force_headless is None:
            is_headless = bool(
                os.environ.get("PYTEST_CURRENT_TEST")
                or os.environ.get("CVCUTTER_HEADLESS") == "1"
            )
        else:
            is_headless = force_headless
        if is_headless:
            return self.first_draft_hint()

        def _main(page: ft.Page) -> None:
            page.title = "CVCutter"
            status = ft.Text(value=self.first_draft_hint())
            job_name = ft.TextField(label="Job Name", value="manual-test-job")
            next_button = ft.Button("Next (Setup Wizard)", disabled=True)

            def _create_draft(_) -> None:
                status.value = self._viewmodel.create_draft(job_name.value or "")
                next_button.disabled = False
                page.update()

            def _go_next(_) -> None:
                status.value = self._viewmodel.go_next()
                page.update()

            next_button.on_click = _go_next
            page.add(
                ft.Text("CVCutter manual-test GUI", size=20),
                status,
                job_name,
                ft.Button("Create Draft", on_click=_create_draft),
                next_button,
            )

        ft.app(target=_main)
        return self._viewmodel.current_state
