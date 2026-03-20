from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RetryDecision:
    event_type: str
    payload: dict[str, object]
    attempt: int
    delay_seconds: int | None = None


@dataclass(slots=True)
class RetryController:
    initial_delay: int = 1
    max_delay: int = 60
    escalation_deadline_seconds: int = 900

    def compute_delay(self, attempt: int, retry_after: int | None = None, jitter: int = 0) -> int:
        if retry_after is not None:
            return max(0, min(retry_after, self.max_delay))
        delay = min(self.initial_delay * (2 ** max(attempt - 1, 0)), self.max_delay)
        return max(0, min(delay + jitter, self.max_delay))

    def should_escalate(self, elapsed_seconds: int) -> bool:
        return elapsed_seconds >= self.escalation_deadline_seconds

    def schedule_retry(
        self,
        *,
        operation_id: str,
        transient_error_code: str,
        attempt: int,
        elapsed_seconds_since_first_failure: int,
        retry_after_seconds: int | None = None,
        jitter: int = 0,
    ) -> RetryDecision:
        delay_seconds = self.compute_delay(attempt, retry_after=retry_after_seconds, jitter=jitter)
        return RetryDecision(
            event_type="retry.scheduled",
            attempt=attempt,
            delay_seconds=delay_seconds,
            payload={
                "operation_id": operation_id,
                "transient_error_code": transient_error_code,
                "attempt": attempt,
                "retry_after_seconds": delay_seconds,
                "strategy": "retry_after_or_exponential_backoff_with_jitter",
                "elapsed_seconds_since_first_failure": elapsed_seconds_since_first_failure,
            },
        )

    def complete_retry(self, *, operation_id: str, attempt: int) -> RetryDecision:
        return RetryDecision(
            event_type="retry.completed",
            attempt=attempt,
            payload={"operation_id": operation_id, "attempt": attempt},
        )

    def escalate_manual(
        self,
        *,
        operation_id: str,
        attempt: int,
        elapsed_seconds_since_first_failure: int,
    ) -> RetryDecision:
        return RetryDecision(
            event_type="retry.escalated_manual",
            attempt=attempt,
            payload={
                "operation_id": operation_id,
                "attempt": attempt,
                "elapsed_seconds_since_first_failure": elapsed_seconds_since_first_failure,
            },
        )
