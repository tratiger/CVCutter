from cvcutter.presentation.flet_app.views.accessibility_view import accessibility_profile


def test_accessibility_flags_enabled() -> None:
    profile = accessibility_profile()
    assert profile["keyboard_navigation"] and profile["focus_visible"] and profile["contrast_safe"]
    assert profile["theme"] == "contrast_safe"
    shortcuts = profile["shortcuts"]
    assert isinstance(shortcuts, list)
    assert "ctrl+enter" in shortcuts
    focus_order = profile["focus_order"]
    assert isinstance(focus_order, list)
    assert focus_order[0] == "source_selector"
    assert profile["wcag_level"] == "AA-equivalent"
