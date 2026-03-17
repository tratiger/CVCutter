from cvcutter.application.services.retry_controller import RetryController


def test_core_service_runs_without_gui_imports() -> None:
    assert RetryController().compute_delay(1) == 1
