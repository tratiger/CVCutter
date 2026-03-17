from __future__ import annotations


class OnboardingView:
    def first_draft_hint(self) -> str:
        return "create_first_draft"

    def run(self) -> str:
        return self.first_draft_hint()
