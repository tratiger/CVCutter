# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportUnusedCoroutine=false
"""Flet load-screen view."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from cvcutter.presentation.viewmodels.load_vm import LoadViewModel


def build_load_view(
    vm: LoadViewModel,
    page: ft.Page | None = None,
    file_picker: ft.FilePicker | None = None,
) -> ft.Column:
    """Build file-loading screen with drag-and-drop and file-picker controls."""
    error_column = ft.Column(spacing=4)
    video_column = ft.Column(spacing=4)

    def refresh_lists() -> None:
        video_column.controls = [ft.Text(str(path), size=12) for path in vm.video_files]
        error_column.controls = [
            ft.Text(message, color=ft.Colors.RED_400, size=12)
            for message in vm.validation_errors
        ]
        if page is not None:
            page.update()

    picker = file_picker or ft.FilePicker()
    if page is not None and picker not in page.overlay:
        page.overlay.append(picker)

    async def pick_files_task() -> None:
        if page is None:
            return
        selected = await picker.pick_files(allow_multiple=True)
        if not selected:
            return
        vm.add_videos([Path(file.path) for file in selected if file.path])
        refresh_lists()

    def on_pick_click(_: ft.ControlEvent) -> None:
        if page is None:
            return
        page.run_task(pick_files_task)

    def on_create_project(_: ft.ControlEvent) -> None:
        try:
            vm.create_project()
        except ValueError:
            refresh_lists()
            return
        refresh_lists()

    drag_target = ft.DragTarget(
        group="files",
        content=ft.Container(
            content=ft.Text("ここに動画ファイルをドラッグ&ドロップ", text_align=ft.TextAlign.CENTER),
            border=ft.border.all(1, ft.Colors.BLUE_300),
            border_radius=8,
            padding=20,
            alignment=ft.Alignment.CENTER,
        ),
        on_accept=lambda _: None,
    )

    refresh_lists()
    return ft.Column(
        controls=[
            ft.Text("ファイル読み込み", size=22, weight=ft.FontWeight.BOLD),
            drag_target,
            ft.Row(
                controls=[
                    ft.ElevatedButton("動画を追加", on_click=on_pick_click),
                    ft.ElevatedButton("プロジェクト作成", on_click=on_create_project),
                ],
                spacing=12,
            ),
            ft.Text("選択済み動画", weight=ft.FontWeight.BOLD),
            ft.Container(content=video_column, padding=10, border=ft.border.all(1, ft.Colors.GREY_700)),
            error_column,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )
