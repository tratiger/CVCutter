from cvcutter.presentation.flet_app.views.accessibility_view import accessibility_profile


def test_accessibility_flags_enabled() -> None:
    profile = accessibility_profile()
    assert profile["keyboard_navigation"] and profile["focus_visible"] and profile["contrast_safe"]
