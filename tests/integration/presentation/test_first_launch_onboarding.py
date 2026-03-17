from cvcutter.presentation.flet_app.views.onboarding_view import OnboardingView


def test_onboarding_first_draft_flow() -> None:
    assert OnboardingView().first_draft_hint() == "create_first_draft"
