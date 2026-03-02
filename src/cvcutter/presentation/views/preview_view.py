# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportUnusedCoroutine=false
"""Flet preview/mapping screen view."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from cvcutter.presentation.viewmodels.preview_vm import PreviewViewModel


def build_preview_view(vm: PreviewViewModel, page: ft.Page | None = None) -> ft.Column:
    """Build FR-063 preview layout with thumbnail/timecode/metadata side-by-side."""
    vm.refresh_notice_from_segments()
    notice_banner = ft.Container(
        visible=bool(vm.reduced_accuracy_notice),
        bgcolor=ft.Colors.AMBER_200,
        padding=10,
        border_radius=6,
        content=ft.Text(vm.reduced_accuracy_notice or ""),
    )
    thumbnails = ft.Column(spacing=8)
    timecodes = ft.Column(spacing=8)
    metadata = ft.Column(spacing=8)

    def selected_segment_id() -> str | None:
        return vm.selected_segment_id or (str(vm.segments[0].id) if vm.segments else None)

    def refresh_layout() -> None:
        thumbnails.controls = [
            ft.Container(
                content=ft.Text(f"サムネイル #{segment.segment_index}", size=12),
                padding=8,
                border=ft.border.all(1, ft.Colors.GREY_700),
                border_radius=6,
            )
            for segment in vm.segments
        ]
        timecodes.controls = [
            ft.Text(
                f"#{segment.segment_index}  {segment.start_time_seconds:.2f}s - {segment.end_time_seconds:.2f}s",
                size=12,
            )
            for segment in vm.segments
        ]
        metadata.controls = [
            ft.Text(
                f"セグメント {segment.segment_index}: "
                f"{vm.mappings.get(str(segment.id), {}).get('program_entry_id') or '未割当'}",
                size=12,
            )
            for segment in vm.segments
        ]
        notice_banner.visible = bool(vm.reduced_accuracy_notice)
        if isinstance(notice_banner.content, ft.Text):
            notice_banner.content.value = vm.reduced_accuracy_notice or ""
        if page is not None:
            page.update()

    def on_select(segment_id: str | None) -> None:
        if not segment_id:
            return
        vm.select_segment(segment_id)
        refresh_layout()

    def on_shift_boundary(_: ft.ControlEvent) -> None:
        segment_id = selected_segment_id()
        if segment_id is None:
            return
        segment = next(item for item in vm.segments if str(item.id) == segment_id)
        vm.adjust_boundary(segment_id, max(0.0, segment.start_time_seconds + 0.5), segment.end_time_seconds + 0.5)
        refresh_layout()

    def on_assign_mapping(_: ft.ControlEvent) -> None:
        segment_id = selected_segment_id()
        if segment_id is None:
            return
        vm.assign_mapping(segment_id, "manual-program")
        refresh_layout()

    refresh_layout()
    segment_options = [
        ft.dropdown.Option(text=f"#{segment.segment_index}", key=str(segment.id))
        for segment in vm.segments
    ]
    selector = ft.Dropdown(
        label="セグメント選択",
        options=segment_options,
        value=selected_segment_id(),
        on_select=lambda event: on_select(event.control.value),
    )
    return ft.Column(
        controls=[
            ft.Text("プレビュー&紐付け", size=22, weight=ft.FontWeight.BOLD),
            notice_banner,
            selector,
            ft.Row(
                controls=[
                    ft.Container(
                        content=thumbnails,
                        expand=1,
                        padding=8,
                        border=ft.border.all(1, ft.Colors.GREY_700),
                        border_radius=6,
                    ),
                    ft.Container(
                        content=timecodes,
                        expand=1,
                        padding=8,
                        border=ft.border.all(1, ft.Colors.GREY_700),
                        border_radius=6,
                    ),
                    ft.Container(
                        content=metadata,
                        expand=1,
                        padding=8,
                        border=ft.border.all(1, ft.Colors.GREY_700),
                        border_radius=6,
                    ),
                ],
                expand=True,
                spacing=10,
            ),
            ft.Row(
                controls=[
                    ft.ElevatedButton("境界を微調整", on_click=on_shift_boundary),
                    ft.ElevatedButton("手動マッピング", on_click=on_assign_mapping),
                ],
                spacing=10,
            ),
        ],
        expand=True,
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
    )
