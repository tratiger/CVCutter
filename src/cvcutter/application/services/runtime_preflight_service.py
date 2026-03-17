from __future__ import annotations


def runtime_profile(acceleration_available: bool) -> str:
    return "accelerated" if acceleration_available else "cpu_fallback"
