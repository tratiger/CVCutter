from __future__ import annotations

import os
import tkinter as tk


class OnboardingView:
    def first_draft_hint(self) -> str:
        return "create_first_draft"

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
            name = job_name.get().strip() or "untitled"
            status.set(f"draft_created:{name}")
            next_button.configure(state="normal")

        def go_next() -> None:
            status.set("setup_wizard_ready")

        create_button = tk.Button(root, text="Create Draft", command=create_draft)
        create_button.pack(pady=6)

        next_button = tk.Button(root, text="Next (Setup Wizard)", state="disabled", command=go_next)
        next_button.pack(pady=6)

        close_button = tk.Button(root, text="Close", command=root.destroy)
        close_button.pack(pady=(10, 12))
        root.mainloop()
        return status.get()
