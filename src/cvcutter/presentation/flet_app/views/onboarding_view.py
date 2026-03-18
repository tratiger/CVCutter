from __future__ import annotations

import os
import tkinter as tk

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

    def run(self) -> str:
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CVCUTTER_HEADLESS") == "1":
            return self.first_draft_hint()
        root = tk.Tk()
        root.title("CVCutter")
        root.geometry("460x260")
        status = tk.StringVar(value=self.first_draft_hint())
        job_name = tk.StringVar(value="manual-test-job")

        header = tk.Label(root, text="CVCutter manual-test GUI", font=("Segoe UI", 14))
        header.pack(pady=(16, 8))

        status_label = tk.Label(root, textvariable=status, font=("Segoe UI", 10))
        status_label.pack(pady=(0, 8))

        form = tk.Frame(root)
        form.pack(pady=8)
        tk.Label(form, text="Job Name:", font=("Segoe UI", 10)).grid(row=0, column=0, padx=6, pady=4)
        tk.Entry(form, textvariable=job_name, width=28).grid(row=0, column=1, padx=6, pady=4)

        def create_draft() -> None:
            status.set(self._viewmodel.create_draft(job_name.get()))
            next_button.configure(state="normal")

        def go_next() -> None:
            status.set(self._viewmodel.go_next())

        create_button = tk.Button(root, text="Create Draft", command=create_draft)
        create_button.pack(pady=6)

        next_button = tk.Button(root, text="Next (Setup Wizard)", state="disabled", command=go_next)
        next_button.pack(pady=6)

        close_button = tk.Button(root, text="Close", command=root.destroy)
        close_button.pack(pady=(10, 12))
        root.mainloop()
        return status.get()
