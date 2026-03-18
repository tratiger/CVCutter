from __future__ import annotations

from dataclasses import dataclass

from cvcutter.infrastructure.persistence.repositories import SqliteRepositories

_ALLOWED_STRATEGIES = {"content_based", "timestamp_based"}


@dataclass(slots=True)
class ClassificationStrategyService:
    repositories: SqliteRepositories

    def set_strategy(self, job_id: str, strategy: str) -> None:
        if strategy not in _ALLOWED_STRATEGIES:
            raise ValueError("unsupported_classification_strategy")
        self.repositories.save_classification_strategy(job_id, strategy)

    def get_strategy(self, job_id: str) -> str:
        stored = self.repositories.load_classification_strategy(job_id)
        return "content_based" if stored is None else stored
