"""Application-layer structured logging helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    import logging


def log_stage_transition(
    logger: logging.Logger,
    stage: str,
    event: str,
    *,
    checkpoint_id: str | None = None,
    input_refs: list[str] | None = None,
    output_refs: list[str] | None = None,
    decision: str | None = None,
    decision_reason: str | None = None,
    duration_ms: float | int | None = None,
    operation_id: str | None = None,
    memory_mb: float | int | None = None,
    disk_free_gb: float | int | None = None,
    cpu_percent: float | int | None = None,
) -> None:
    """Emit a structured stage-transition log entry."""
    logger.info(
        "%s %s",
        stage,
        event,
        extra={
            "operation_id": operation_id or str(uuid4()),
            "pipeline_stage": stage,
            "checkpoint_id": checkpoint_id,
            "event": event,
            "input_refs": list(input_refs) if input_refs is not None else None,
            "output_refs": list(output_refs) if output_refs is not None else None,
            "decision": decision,
            "decision_reason": decision_reason,
            "duration_ms": duration_ms,
            "memory_mb": _safe_float(memory_mb),
            "disk_free_gb": _safe_float(disk_free_gb),
            "cpu_percent": _safe_float(cpu_percent),
        },
    )


def log_resource_telemetry(
    logger: logging.Logger,
    stage: str,
    *,
    path: Path | None = None,
    operation_id: str | None = None,
    memory_mb: float | int | None = None,
    disk_free_gb: float | int | None = None,
    cpu_percent: float | int | None = None,
) -> None:
    """Emit standardized resource telemetry for memory, disk, and CPU usage."""
    resolved_memory_mb, resolved_cpu_percent = _process_metrics()
    resolved_disk_free_gb = _disk_free_gb(path or Path.cwd())
    log_stage_transition(
        logger,
        stage=stage,
        event="RESOURCE_TELEMETRY",
        operation_id=operation_id,
        memory_mb=_coalesce_metric(memory_mb, resolved_memory_mb),
        disk_free_gb=_coalesce_metric(disk_free_gb, resolved_disk_free_gb),
        cpu_percent=_coalesce_metric(cpu_percent, resolved_cpu_percent),
    )


def _process_metrics() -> tuple[float | None, float | None]:
    try:
        import psutil

        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / (1024**2)
        cpu_percent = psutil.cpu_percent(interval=0.0)
        return memory_mb, cpu_percent
    except Exception:
        return None, None


def _disk_free_gb(path: Path) -> float | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return usage.free / (1024**3)


def _safe_float(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coalesce_metric(primary: float | int | None, fallback: float | None) -> float | None:
    resolved_primary = _safe_float(primary)
    if resolved_primary is not None:
        return resolved_primary
    return _safe_float(fallback)
