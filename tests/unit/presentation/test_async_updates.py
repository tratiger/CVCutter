"""Responsiveness and progress callback tests for presentation layer (T064)."""

from __future__ import annotations

import asyncio
import threading
from time import perf_counter, sleep

import flet as ft

from cvcutter.domain.services.types import ProgressEvent
from cvcutter.presentation.viewmodels.process_vm import ProcessViewModel
from cvcutter.presentation.views.process_view import build_process_view


class _MockProcessingWorkflow:
    """Minimal processing workflow stub."""

    def start(self, project_id: str, progress_callback) -> list[object]:
        del project_id
        for index in range(5):
            progress_callback(
                ProgressEvent(
                    stage="DETECTION",
                    current=index + 1,
                    total=5,
                    message=f"進捗 {index + 1}/5",
                ),
            )
        return []

    def resume(self, project_id: str, progress_callback) -> list[object]:
        return self.start(project_id, progress_callback)

    def pause(self) -> None:
        return

    def cancel(self) -> None:
        return


class _FakePage:
    def __init__(self) -> None:
        self.update_calls = 0

    def update(self) -> None:
        self.update_calls += 1

    def run_task(self, coroutine_factory) -> None:
        asyncio.run(coroutine_factory())


def test_responsiveness_callback_timing() -> None:
    vm = ProcessViewModel(workflow=_MockProcessingWorkflow())
    event = ProgressEvent(stage="EXPORT", current=1, total=2, message="エクスポート中")

    start = perf_counter()
    vm.on_progress(event)
    elapsed_ms = (perf_counter() - start) * 1000

    assert elapsed_ms < 100


def test_sc006_interaction_target_500ms_scaffold() -> None:
    vm = ProcessViewModel(workflow=_MockProcessingWorkflow())

    start = perf_counter()
    vm.pause_processing()
    elapsed_ms = (perf_counter() - start) * 1000

    assert elapsed_ms <= 500


def test_progress_updates_do_not_block_ui() -> None:
    vm = ProcessViewModel(workflow=_MockProcessingWorkflow())

    def emit_progress() -> None:
        for index in range(100):
            vm.on_progress(
                ProgressEvent(stage="DETECTION", current=index + 1, total=100, message="処理中"),
            )

    worker = threading.Thread(target=emit_progress)
    worker.start()

    start = perf_counter()
    vm.cancel_processing()
    elapsed_ms = (perf_counter() - start) * 1000
    worker.join(timeout=1.0)

    assert elapsed_ms <= 500
    assert worker.is_alive() is False


def test_process_view_refreshes_during_background_processing() -> None:
    class _SlowProcessingWorkflow(_MockProcessingWorkflow):
        def start(self, project_id: str, progress_callback) -> list[object]:
            del project_id
            for index in range(3):
                progress_callback(
                    ProgressEvent(
                        stage="DETECTION",
                        current=index + 1,
                        total=3,
                        message=f"進捗 {index + 1}/3",
                    ),
                )
                sleep(0.12)
            return []

    vm = ProcessViewModel(workflow=_SlowProcessingWorkflow())
    page = _FakePage()
    view = build_process_view(vm, page)
    action_row = next(
        control
        for control in view.controls
        if isinstance(control, ft.Row)
        and any(isinstance(button, ft.ElevatedButton) for button in control.controls)
    )
    start_button = next(
        button
        for button in action_row.controls
        if isinstance(button, ft.ElevatedButton) and button.content == "開始"
    )

    start_button.on_click(None)

    assert page.update_calls > 2
