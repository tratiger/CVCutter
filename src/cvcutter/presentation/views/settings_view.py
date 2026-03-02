# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportUnusedCoroutine=false
"""Flet settings-screen view."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from cvcutter.presentation.viewmodels.settings_vm import SettingsViewModel


def build_settings_view(vm: SettingsViewModel, page: ft.Page | None = None) -> ft.Column:
    """Build settings form with authentication and artifact controls."""
    status_text = ft.Text(vm.status_message)
    yolo_toggle = ft.Switch(
        label="YOLO検出を有効化",
        value=bool(vm.config.enable_yolo_detection) if vm.config is not None else True,
    )
    gemini_toggle = ft.Switch(
        label="Gemini連携を有効化",
        value=bool(vm.config.enable_gemini) if vm.config is not None else True,
    )
    volume_slider = ft.Slider(
        min=0.0,
        max=2.0,
        divisions=20,
        value=float(vm.config.video_audio_volume) if vm.config is not None else 0.6,
        label="{value}",
    )
    retention_dropdown = ft.Dropdown(
        label="成果物保持ポリシー",
        value="auto-clean",
        options=[
            ft.dropdown.Option("auto-clean", "自動削除"),
            ft.dropdown.Option("retain", "保持"),
        ],
    )

    def refresh() -> None:
        status_text.value = vm.status_message
        if vm.config is not None:
            yolo_toggle.value = vm.config.enable_yolo_detection
            gemini_toggle.value = vm.config.enable_gemini
            volume_slider.value = vm.config.video_audio_volume
        if page is not None:
            page.update()

    def on_save(_: ft.ControlEvent) -> None:
        vm.update_config("enable_yolo_detection", bool(yolo_toggle.value))
        vm.update_config("enable_gemini", bool(gemini_toggle.value))
        vm.update_config("video_audio_volume", float(volume_slider.value))
        refresh()

    def on_auth(_: ft.ControlEvent) -> None:
        vm.authenticate()
        refresh()

    def on_test(_: ft.ControlEvent) -> None:
        vm.test_connection()
        refresh()

    def on_retention(_: ft.ControlEvent) -> None:
        value = retention_dropdown.value or "auto-clean"
        vm.set_artifact_retention(value)
        refresh()

    def on_purge(_: ft.ControlEvent) -> None:
        vm.purge_artifacts(vm.active_project_id)
        refresh()

    refresh()
    return ft.Column(
        controls=[
            ft.Text("設定", size=22, weight=ft.FontWeight.BOLD),
            yolo_toggle,
            gemini_toggle,
            ft.Text("動画音量"),
            volume_slider,
            ft.ElevatedButton("設定を保存", on_click=on_save),
            ft.Divider(),
            ft.Text("認証・接続", weight=ft.FontWeight.BOLD),
            ft.Row(
                controls=[
                    ft.ElevatedButton("認証", on_click=on_auth),
                    ft.OutlinedButton("接続テスト", on_click=on_test),
                ],
                spacing=10,
            ),
            ft.Divider(),
            ft.Text("成果物管理", weight=ft.FontWeight.BOLD),
            retention_dropdown,
            ft.Row(
                controls=[
                    ft.ElevatedButton("保持ポリシー更新", on_click=on_retention),
                    ft.OutlinedButton("成果物を削除", on_click=on_purge),
                ],
                spacing=10,
            ),
            status_text,
        ],
        expand=True,
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
    )
