from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RetryController:
    initial_delay: int = 1
    max_delay: int = 60

    def compute_delay(self, attempt: int, retry_after: int | None = None, jitter: int = 0) -> int:
        if retry_after is not None:
            return max(0, min(retry_after, self.max_delay))
        delay = min(self.initial_delay * (2 ** max(attempt - 1, 0)), self.max_delay)
        return max(0, min(delay + jitter, self.max_delay))

    def should_escalate(self, elapsed_seconds: int) -> bool:
        return elapsed_seconds >= 900
