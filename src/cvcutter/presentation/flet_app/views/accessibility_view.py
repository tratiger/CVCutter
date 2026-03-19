from __future__ import annotations


def accessibility_profile() -> dict[str, object]:
    return {
        "keyboard_navigation": True,
        "focus_visible": True,
        "contrast_safe": True,
        "theme": "contrast_safe",
        "shortcuts": ["ctrl+enter", "alt+up", "alt+down"],
        "focus_order": [
            "source_selector",
            "metadata_selector",
            "strategy_selector",
            "start_button",
        ],
        "wcag_level": "AA-equivalent",
    }
