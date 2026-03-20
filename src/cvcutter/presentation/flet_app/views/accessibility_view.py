from __future__ import annotations

import flet as ft

from cvcutter.presentation.flet_app.viewmodel_helpers import localized


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


def build_accessibility_controls() -> list[ft.Control]:
    profile = accessibility_profile()
    shortcuts = profile["shortcuts"] if isinstance(profile["shortcuts"], list) else []
    focus_order = profile["focus_order"] if isinstance(profile["focus_order"], list) else []
    return [
        ft.Text(localized("accessibility.title"), size=20),
        ft.Text(f"Keyboard only: {profile['keyboard_navigation']}"),
        ft.Text(f"Focus visible: {profile['focus_visible']}"),
        ft.Text(f"Contrast safe: {profile['contrast_safe']}"),
        ft.Text(f"Shortcuts: {', '.join(str(item) for item in shortcuts)}"),
        ft.Text(f"Focus order: {', '.join(str(item) for item in focus_order)}"),
        ft.Text(f"WCAG: {profile['wcag_level']}"),
    ]
