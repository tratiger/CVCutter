from __future__ import annotations


def accessibility_profile() -> dict[str, object]:
    return {
        "keyboard_navigation": True,
        "focus_visible": True,
        "contrast_safe": True,
        "theme": "contrast_safe",
        "shortcuts": ["ctrl+enter", "alt+up", "alt+down"],
    }
