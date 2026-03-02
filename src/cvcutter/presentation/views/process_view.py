# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportUnusedCoroutine=false
"""Flet process-screen view."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from cvcutter.presentation.viewmodels.process_vm import ProcessViewModel


def build_process_view(vm: ProcessViewModel, page: ft.Page | None = None) -> ft.Column:
    """Build processing screen with progress and stage indicators."""
    stage_text = ft.Text(vm.current_stage)
    operation_text = ft.Text(vm.current_operation)
    detection_mode_text = ft.Text(f"検出モード: {vm.detection_mode}")
    stage_progress = ft.ProgressBar(value=vm.stage_progress)
    overall_progress = ft.ProgressBar(value=vm.overall_progress)
    notice_banner = ft.Container(
        visible=bool(vm.reduced_accuracy_notice),
        bgcolor=ft.Colors.AMBER_200,
        padding=10,
        border_radius=6,
        content=ft.Text(vm.reduced_accuracy_notice or ""),
    )
    segment_list = ft.Column(spacing=4)
    start_button = ft.ElevatedButton("開始")
    resume_button = ft.ElevatedButton("再開")
    pause_button = ft.OutlinedButton("一時停止")
    cancel_button = ft.OutlinedButton("キャンセル")

    def refresh() -> None:
        stage_text.value = f"現在ステージ: {vm.current_stage}"
        operation_text.value = f"処理内容: {vm.current_operation}"
        detection_mode_text.value = f"検出モード: {vm.detection_mode}"
        stage_progress.value = vm.stage_progress
        overall_progress.value = vm.overall_progress
        notice_banner.visible = bool(vm.reduced_accuracy_notice)
        if isinstance(notice_banner.content, ft.Text):
            notice_banner.content.value = vm.reduced_accuracy_notice or ""
        segment_list.controls = [
            ft.Text(
                f"#{segment.segment_index} {segment.start_time_seconds:.1f}s - "
                f"{segment.end_time_seconds:.1f}s ({segment.effective_detection_mode})",
                size=12,
            )
            for segment in vm.detected_segments
        ]
        start_button.disabled = vm.is_processing
        resume_button.disabled = vm.is_processing
        pause_button.disabled = not vm.is_processing
        cancel_button.disabled = not vm.is_processing
        if page is not None:
            page.update()

    async def run_start() -> None:
        await asyncio.to_thread(vm.start_processing)
        refresh()

    async def run_resume() -> None:
        await asyncio.to_thread(vm.resume_processing)
        refresh()

    def on_start(_: ft.ControlEvent) -> None:
        if vm.is_processing:
            return
        if page is None:
            vm.start_processing()
            refresh()
            return
        page.run_task(run_start)

    def on_resume(_: ft.ControlEvent) -> None:
        if vm.is_processing:
            return
        if page is None:
            vm.resume_processing()
            refresh()
            return
        page.run_task(run_resume)

    def on_pause(_: ft.ControlEvent) -> None:
        if not vm.is_processing:
            return
        vm.pause_processing()
        refresh()

    def on_cancel(_: ft.ControlEvent) -> None:
        if not vm.is_processing:
            return
        vm.cancel_processing()
        refresh()

    start_button.on_click = on_start
    resume_button.on_click = on_resume
    pause_button.on_click = on_pause
    cancel_button.on_click = on_cancel

    stage_chips = ft.Row(
        controls=[
            ft.Chip(label=ft.Text("連結")),
            ft.Chip(label=ft.Text("検出")),
            ft.Chip(label=ft.Text("音声同期")),
            ft.Chip(label=ft.Text("書き出し")),
            ft.Chip(label=ft.Text("紐付け")),
            ft.Chip(label=ft.Text("アップロード")),
        ],
        wrap=True,
        spacing=8,
    )
    refresh()
    return ft.Column(
        controls=[
            ft.Text("動画処理", size=22, weight=ft.FontWeight.BOLD),
            stage_chips,
            notice_banner,
            stage_text,
            operation_text,
            detection_mode_text,
            ft.Text("ステージ進捗"),
            stage_progress,
            ft.Text("全体進捗"),
            overall_progress,
            ft.Row(
                controls=[
                    start_button,
                    resume_button,
                    pause_button,
                    cancel_button,
                ],
                spacing=8,
            ),
            ft.Text("検出セグメント", weight=ft.FontWeight.BOLD),
            segment_list,
        ],
        expand=True,
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
    )
