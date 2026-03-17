from __future__ import annotations


class ClassificationStrategyService:
    def __init__(self) -> None:
        self._strategies: dict[str, str] = {}

    def set_strategy(self, job_id: str, strategy: str) -> None:
        self._strategies[job_id] = strategy

    def get_strategy(self, job_id: str) -> str:
        return self._strategies.get(job_id, "name+program")
