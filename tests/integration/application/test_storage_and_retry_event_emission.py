from __future__ import annotations

from cvcutter.application.services.retry_controller import RetryController
from cvcutter.application.services.storage_safety_service import evaluate_storage_policy


def test_storage_policy_emits_warning_block_pause_events() -> None:
    warning = evaluate_storage_policy(19)
    blocked = evaluate_storage_policy(9)
    pause = evaluate_storage_policy(4)

    assert warning.event_type == "storage.threshold_warning"
    assert warning.policy == "warning"
    assert warning.payload["free_gb"] == 19
    assert warning.payload["threshold_gb"] == 20
    assert warning.payload["action_taken"] == "warn_and_continue"

    assert blocked.event_type == "storage.threshold_block"
    assert blocked.policy == "start_blocked"
    assert blocked.payload["free_gb"] == 9
    assert blocked.payload["threshold_gb"] == 10
    assert blocked.payload["action_taken"] == "block_new_starts"

    assert pause.event_type == "storage.threshold_pause"
    assert pause.policy == "safe_pause"
    assert pause.payload["free_gb"] == 4
    assert pause.payload["threshold_gb"] == 5
    assert pause.payload["action_taken"] == "pause_active_job"


def test_retry_controller_emits_schedule_completed_and_escalation_events() -> None:
    controller = RetryController()

    scheduled = controller.schedule_retry(
        operation_id="publish:job:segment:youtube",
        transient_error_code="HTTP_429",
        attempt=1,
        elapsed_seconds_since_first_failure=120,
        retry_after_seconds=17,
    )
    assert scheduled.event_type == "retry.scheduled"
    assert scheduled.attempt == 1
    assert scheduled.delay_seconds == 17
    assert scheduled.payload["operation_id"] == "publish:job:segment:youtube"
    assert scheduled.payload["attempt"] == 1
    assert scheduled.payload["strategy"] == "retry_after_or_exponential_backoff_with_jitter"

    completed = controller.complete_retry(
        operation_id="publish:job:segment:youtube",
        attempt=2,
    )
    assert completed.event_type == "retry.completed"
    assert completed.attempt == 2
    assert completed.payload["operation_id"] == "publish:job:segment:youtube"
    assert completed.payload["attempt"] == 2

    escalated = controller.escalate_manual(
        operation_id="publish:job:segment:youtube",
        attempt=3,
        elapsed_seconds_since_first_failure=901,
    )
    assert escalated.event_type == "retry.escalated_manual"
    assert escalated.attempt == 3
    assert escalated.payload["operation_id"] == "publish:job:segment:youtube"
    assert escalated.payload["attempt"] == 3
    assert escalated.payload["elapsed_seconds_since_first_failure"] == 901
