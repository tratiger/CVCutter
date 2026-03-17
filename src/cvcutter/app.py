from __future__ import annotations

from dataclasses import dataclass

from cvcutter.infrastructure.packaging.platform_compatibility import PlatformCompatibilityChecker
from cvcutter.presentation.flet_app.views.onboarding_view import OnboardingView


@dataclass(slots=True)
class AppBootstrap:
    checker: PlatformCompatibilityChecker

    def launch(self) -> dict[str, str | bool]:
        result = self.checker.ensure_supported()
        if not result["supported"]:
            return {"status": "blocked", "reason": result["reason"]}
        return {"status": "ready", "next": OnboardingView().first_draft_hint()}


def run_runtime(bootstrap: AppBootstrap) -> int:
    launch_result = bootstrap.launch()
    if launch_result["status"] != "ready":
        return 1
    OnboardingView().run()
    return 0


def main() -> int:
    bootstrap = AppBootstrap(checker=PlatformCompatibilityChecker())
    return run_runtime(bootstrap)


if __name__ == "__main__":
    raise SystemExit(main())
