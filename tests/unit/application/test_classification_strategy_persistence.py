from __future__ import annotations

from pathlib import Path

import pytest

from cvcutter.application.services.classification_strategy_service import ClassificationStrategyService
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories

JOB_ID = "11111111-1111-1111-1111-111111111111"


def _repo(tmp_path: Path) -> SqliteRepositories:
    repo = SqliteRepositories(tmp_path / "strategy.db")
    repo.init_schema()
    return repo


def test_strategy_persists_across_service_instances(tmp_path: Path) -> None:
    first = ClassificationStrategyService(_repo(tmp_path))
    first.set_strategy(JOB_ID, "timestamp_based")

    second = ClassificationStrategyService(_repo(tmp_path))
    assert second.get_strategy(JOB_ID) == "timestamp_based"


def test_invalid_strategy_is_rejected(tmp_path: Path) -> None:
    service = ClassificationStrategyService(_repo(tmp_path))
    with pytest.raises(ValueError):
        service.set_strategy(JOB_ID, "unknown_strategy")
