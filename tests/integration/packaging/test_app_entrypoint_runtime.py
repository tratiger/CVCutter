from __future__ import annotations

from cvcutter.app import AppBootstrap, run_runtime
from cvcutter.infrastructure.packaging.platform_compatibility import PlatformCompatibilityChecker
from cvcutter.presentation.flet_app.views.onboarding_view import OnboardingView


class _SupportedChecker(PlatformCompatibilityChecker):
    def ensure_supported(self) -> dict[str, str | bool]:
        return {"supported": True, "reason": "ok"}


class _UnsupportedChecker(PlatformCompatibilityChecker):
    def ensure_supported(self) -> dict[str, str | bool]:
        return {"supported": False, "reason": "unsupported_os"}


def test_run_runtime_executes_onboarding(monkeypatch) -> None:
    observed: dict[str, bool] = {"ran": False}

    def _run(self: OnboardingView) -> str:
        observed["ran"] = True
        return "create_first_draft"

    monkeypatch.setattr(OnboardingView, "run", _run)
    exit_code = run_runtime(AppBootstrap(checker=_SupportedChecker()))
    assert exit_code == 0
    assert observed["ran"]


def test_run_runtime_blocks_on_unsupported_platform() -> None:
    exit_code = run_runtime(AppBootstrap(checker=_UnsupportedChecker()))
    assert exit_code == 1
