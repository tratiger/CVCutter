"""Processing benchmark scaffolding for SC-001 (T127)."""

from __future__ import annotations

import pytest

from tests.conftest import make_project_id

pytestmark = [pytest.mark.benchmark, pytest.mark.slow]


def test_sc001_processing_speed_benchmark_scaffold() -> None:
    benchmark_run_id = make_project_id()
    pytest.skip(
        f"SC-001 benchmark placeholder for run {benchmark_run_id}; timing thresholds added in later tasks.",
    )


def test_sc001_processing_speed_threshold_scaffold_gpu_and_cpu() -> None:
    benchmark_run_id = make_project_id()
    pytest.skip(
        "SC-001 threshold scaffold "
        f"for run {benchmark_run_id}: validate GPU <60 min and CPU <150 min for 2h 1080p input.",
    )
