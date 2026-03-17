from cvcutter.application.services.retry_controller import RetryController


def test_retry_after_wins() -> None:
    controller = RetryController()
    assert controller.compute_delay(attempt=3, retry_after=7) == 7


def test_backoff_and_escalation() -> None:
    controller = RetryController()
    assert controller.compute_delay(attempt=1) == 1
    assert controller.compute_delay(attempt=10) == 60
    assert controller.should_escalate(900)


def test_negative_retry_after_is_clamped_to_zero() -> None:
    controller = RetryController()
    assert controller.compute_delay(attempt=1, retry_after=-5) == 0
