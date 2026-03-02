"""Installer launch-time validation scaffold for SC-007 (T125)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_SC007_MAX_SECONDS = 5.0


def test_clean_machine_launch_time_scaffold() -> None:
    """Validate first-window render time on a clean machine is within SC-007."""
    metrics_path = Path("test-output") / "installer-launch-metrics.json"
    if not metrics_path.exists():
        pytest.skip("No installer launch metrics found; run tools/validate_installer.ps1 first.")

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    launch_seconds = float(payload["launch_seconds"])
    assert launch_seconds <= _SC007_MAX_SECONDS
