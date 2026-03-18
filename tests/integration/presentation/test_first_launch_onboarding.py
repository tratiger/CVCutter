from pathlib import Path

from cvcutter.presentation.controllers.cleanup_controller import CleanupController
from cvcutter.presentation.flet_app.views.onboarding_view import OnboardingView


def test_onboarding_first_draft_flow() -> None:
    view = OnboardingView()
    assert view.first_draft_hint() == "create_first_draft"
    assert view.preview_progression("first-job") == [
        "create_first_draft",
        "draft_created:first-job",
        "setup_wizard_ready",
    ]


def test_onboarding_runtime_uses_flet_app(monkeypatch) -> None:
    observed = {"called": False}

    def _fake_app(target) -> None:
        observed["called"] = True

        class _DummyPage:
            title: str = ""
            window_width: int = 0
            window_height: int = 0

            def add(self, *args, **kwargs) -> None:
                return None

            def update(self) -> None:
                return None

        target(_DummyPage())

    monkeypatch.setattr("cvcutter.presentation.flet_app.views.onboarding_view.ft.app", _fake_app)
    result = OnboardingView().run(force_headless=False)
    assert observed["called"]
    assert result == "create_first_draft"


def test_cleanup_controller_returns_structured_contract_payload(tmp_path: Path) -> None:
    artifact = tmp_path / "scratch.log"
    artifact.write_text("temporary", encoding="utf-8")
    controller = CleanupController(managed_root=tmp_path)
    performed = controller.request_cleanup("scratch.log")
    assert performed["event_type"] == "cleanup.performed"
    assert performed["actor_role"] == "operator"
    assert performed["target_class"] == "deletable_artifact"
    assert performed["outcome"] == "performed"
    assert performed["reason"] == "user_requested"
    assert not artifact.exists()

    rejected = controller.request_cleanup("audit:event-1")
    assert rejected["event_type"] == "cleanup.rejected"
    assert rejected["target_class"] == "protected_minimal_audit"
    assert rejected["outcome"] == "rejected"
    assert rejected["reason"] == "policy_protected"
