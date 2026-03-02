"""Resource-efficiency benchmark scaffolds for US8 (T085)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.benchmark, pytest.mark.slow]

_FOUR_K_MEMORY_LIMIT_MB = 4096
_FULL_HD_MEMORY_LIMIT_MB = 2048
_TEMP_DISK_MULTIPLIER_LIMIT = 2.0


def _load_resource_metrics() -> dict[str, float]:
    metrics_path = Path("test-output") / "resource-efficiency-metrics.json"
    if not metrics_path.exists():
        pytest.skip("Resource benchmark metrics not found; run benchmark harness first.")
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    return {
        "peak_memory_4k_mb": float(payload["peak_memory_4k_mb"]),
        "peak_memory_1080p_mb": float(payload["peak_memory_1080p_mb"]),
        "temp_disk_bytes": float(payload["temp_disk_bytes"]),
        "source_bytes": float(payload["source_bytes"]),
    }


def test_peak_memory_constraints_scaffold() -> None:
    """Validate peak memory stays within 4K/1080p benchmark thresholds."""
    metrics = _load_resource_metrics()
    assert metrics["peak_memory_4k_mb"] < _FOUR_K_MEMORY_LIMIT_MB
    assert metrics["peak_memory_1080p_mb"] < _FULL_HD_MEMORY_LIMIT_MB


def test_temp_disk_usage_within_2x_source_scaffold() -> None:
    """Validate temporary disk usage does not exceed 2x source size."""
    metrics = _load_resource_metrics()
    assert metrics["source_bytes"] > 0
    assert metrics["temp_disk_bytes"] <= metrics["source_bytes"] * _TEMP_DISK_MULTIPLIER_LIMIT
