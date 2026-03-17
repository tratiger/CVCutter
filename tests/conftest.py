from __future__ import annotations

from pathlib import Path

import pytest

from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


@pytest.fixture
def sqlite_repo(tmp_path: Path) -> SqliteRepositories:
    repo = SqliteRepositories(tmp_path / "test.db")
    repo.init_schema()
    return repo
