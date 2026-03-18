from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OnboardingFlowViewModel:
    current_state: str = "create_first_draft"
    _draft_created: bool = False

    def create_draft(self, job_name: str) -> str:
        normalized_name = job_name.strip() or "untitled"
        self._draft_created = True
        self.current_state = f"draft_created:{normalized_name}"
        return self.current_state

    def go_next(self) -> str:
        if not self._draft_created:
            self.current_state = "blocked:create_draft_first"
            return self.current_state
        self.current_state = "setup_wizard_ready"
        return self.current_state
