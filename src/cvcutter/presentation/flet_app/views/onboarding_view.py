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
        root.geometry("420x180")
        label = tk.Label(root, text="CVCutter manual-test GUI", font=("Segoe UI", 14))
        label.pack(pady=24)
        hint = tk.Label(root, text=self.first_draft_hint(), font=("Segoe UI", 10))
        hint.pack(pady=8)
        start_button = tk.Button(root, text="Close", command=root.destroy)
        start_button.pack(pady=8)
        root.mainloop()
        return self.first_draft_hint()
