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


def test_cleanup_controller_returns_structured_contract_payload() -> None:
    controller = CleanupController()
    performed = controller.request_cleanup("scratch:file-1")
    assert performed["event_type"] == "cleanup.performed"
    assert performed["actor_role"] == "operator"
    assert performed["target_class"] == "deletable_artifact"
    assert performed["outcome"] == "performed"
    assert performed["reason"] == "user_requested"

    rejected = controller.request_cleanup("audit:event-1")
    assert rejected["event_type"] == "cleanup.rejected"
    assert rejected["target_class"] == "protected_minimal_audit"
    assert rejected["outcome"] == "rejected"
    assert rejected["reason"] == "policy_protected"
