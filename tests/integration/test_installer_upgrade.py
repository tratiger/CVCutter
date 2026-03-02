"""Installer upgrade validation scaffolds for US7 (T080)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_upgrade_preserves_settings_scaffold(tmp_path) -> None:
    """Scaffold for validating persisted settings survive an installer upgrade."""
    del tmp_path
    pytest.skip("Upgrade scenario harness is not wired yet; add installer e2e orchestration in a follow-up.")
