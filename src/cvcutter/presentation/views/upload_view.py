# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportUnusedCoroutine=false
"""Flet upload-screen view."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import flet as ft

from cvcutter.shared.types import UploadStatus

if TYPE_CHECKING:
    from cvcutter.presentation.viewmodels.upload_vm import UploadViewModel


def build_upload_view(vm: UploadViewModel, page: ft.Page | None = None) -> ft.Column:
    """Build upload screen with status list, URLs, and quota meter."""
    record_column = ft.Column(spacing=6)
    operation_text = ft.Text(vm.current_operation)
    quota_text = ft.Text(vm.quota_display)
    quota_bar = ft.ProgressBar(
        value=0.0
        if vm.quota_state_snapshot.daily_limit == 0
        else vm.quota_state_snapshot.daily_used / vm.quota_state_snapshot.daily_limit,
    )
    start_button = ft.ElevatedButton("アップロード開始")
    pause_button = ft.OutlinedButton("一時停止")
    retry_button = ft.OutlinedButton("失敗を再試行")

    def refresh() -> None:
        try:
            vm.refresh_quota()
        except Exception as exc:
            vm.errors.append(f"クォータ表示更新に失敗しました: {exc}")
            vm.current_operation = "クォータ情報の取得に失敗しました。"
        operation_text.value = vm.current_operation
        quota_text.value = vm.quota_display
        quota_bar.value = (
            0.0
            if vm.quota_state_snapshot.daily_limit == 0
            else vm.quota_state_snapshot.daily_used / vm.quota_state_snapshot.daily_limit
        )
        record_column.controls = []
        for record in vm.upload_records:
            link = (
                ft.TextButton("YouTubeを開く", url=record.youtube_url)
                if record.youtube_url
                else ft.Text("-", size=12)
            )
            record_column.controls.append(
                ft.Row(
                    controls=[
                        ft.Text(record.id[:8], size=12),
                        ft.Text(record.upload_status.value, size=12),
                        link,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            )
        has_failed = any(record.upload_status == UploadStatus.FAILED for record in vm.upload_records)
        start_button.disabled = vm.is_uploading
        pause_button.disabled = not vm.is_uploading
        retry_button.disabled = vm.is_uploading or not has_failed
        if page is not None:
            page.update()

    async def run_start() -> None:
        await asyncio.to_thread(vm.start_upload)
        refresh()

    def on_start(_: ft.ControlEvent) -> None:
        if vm.is_uploading:
            return
        if page is None:
            vm.start_upload()
            refresh()
            return
        page.run_task(run_start)

    def on_pause(_: ft.ControlEvent) -> None:
        if not vm.is_uploading:
            return
        vm.pause()
        refresh()

    def on_retry(_: ft.ControlEvent) -> None:
        failed = next(
            (record for record in vm.upload_records if record.upload_status == UploadStatus.FAILED),
            None,
        )
        if failed is None:
            return
        vm.retry_failed(failed.id)
        refresh()

    start_button.on_click = on_start
    pause_button.on_click = on_pause
    retry_button.on_click = on_retry

    refresh()
    return ft.Column(
        controls=[
            ft.Text("アップロード", size=22, weight=ft.FontWeight.BOLD),
            quota_text,
            quota_bar,
            ft.Row(
                controls=[
                    start_button,
                    pause_button,
                    retry_button,
                ],
                spacing=10,
            ),
            operation_text,
            ft.Text("アップロード状況", weight=ft.FontWeight.BOLD),
            record_column,
        ],
        expand=True,
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
    )
