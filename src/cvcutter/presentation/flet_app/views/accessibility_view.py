from __future__ import annotations


def accessibility_profile() -> dict[str, bool]:
    return {"keyboard_navigation": True, "focus_visible": True, "contrast_safe": True}
