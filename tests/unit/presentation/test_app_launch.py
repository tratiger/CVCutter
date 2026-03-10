"""Unit tests for presentation app launcher behavior."""

from __future__ import annotations

import flet as ft

from cvcutter.presentation import app as app_module


def test_launch_uses_desktop_app_view(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_app(*args, **kwargs) -> None:
        captured["target"] = kwargs.get("target")
        captured["view"] = kwargs.get("view")

    monkeypatch.setattr(app_module.ft, "app", _fake_app)

    app_module.launch()

    assert captured["target"] is app_module._build_page
    assert captured["view"] == ft.AppView.FLET_APP
