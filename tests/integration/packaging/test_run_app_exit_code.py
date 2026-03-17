from __future__ import annotations

import runpy
from pathlib import Path

import pytest

import cvcutter.app as app_module


def test_run_app_propagates_main_exit_code(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "main", lambda: 1)
    script_path = Path(__file__).resolve().parents[3] / "run_app.py"
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(script_path), run_name="__main__")
    assert exit_info.value.code == 1
