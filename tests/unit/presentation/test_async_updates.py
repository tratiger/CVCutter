"""Responsiveness and progress callback tests for presentation layer (T064)."""

from __future__ import annotations

import threading
from time import perf_counter

from cvcutter.domain.services.types import ProgressEvent
from cvcutter.presentation.viewmodels.process_vm import ProcessViewModel


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
