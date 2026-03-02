"""Structured JSON logging utilities for pipeline observability."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

DEFAULT_PROJECT_ID = "default"
PROJECT_ID_ENV_VAR = "CVCUTTER_PROJECT_ID"
_PIPELINE_FILE_HANDLER_NAME = "cvcutter.pipeline_jsonl"
_CONSOLE_HANDLER_NAME = "cvcutter.console"


class JsonFormatter(logging.Formatter):
    """Format log records as a JSON object for JSONL pipeline logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record to a JSON string."""
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "operation_id": getattr(record, "operation_id", None),
            "pipeline_stage": getattr(record, "pipeline_stage", None),
            "checkpoint_id": getattr(record, "checkpoint_id", None),
            "event": getattr(record, "event", None),
            "input_refs": self._normalize_refs(getattr(record, "input_refs", None)),
            "output_refs": self._normalize_refs(getattr(record, "output_refs", None)),
            "decision": getattr(record, "decision", None),
            "decision_reason": getattr(record, "decision_reason", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "memory_mb": _safe_float(getattr(record, "memory_mb", None)),
            "disk_free_gb": _safe_float(getattr(record, "disk_free_gb", None)),
            "cpu_percent": _safe_float(getattr(record, "cpu_percent", None)),
            "message": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _normalize_refs(value: Any) -> list[str] | None:
        """Normalize reference fields to a list of strings."""
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]


def init_logging(log_dir: Path | None = None) -> None:
    """Initialize root logger with JSONL file and development console handlers."""
    target_dir = log_dir or _default_log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    project_id = _sanitize_project_id(os.getenv(PROJECT_ID_ENV_VAR, DEFAULT_PROJECT_ID))
    log_path = target_dir / f"pipeline_{project_id}.jsonl"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    managed_handlers = [handler for handler in root_logger.handlers if handler.name in _handler_names()]
    for handler in managed_handlers:
        handler.close()
    root_logger.handlers = [h for h in root_logger.handlers if h.name not in _handler_names()]

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.name = _PIPELINE_FILE_HANDLER_NAME
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JsonFormatter())

    console_handler = logging.StreamHandler()
    console_handler.name = _CONSOLE_HANDLER_NAME
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_pipeline_logger(name: str) -> logging.Logger:
    """Return a named logger for pipeline components."""
    return logging.getLogger(name)


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


def _default_log_dir() -> Path:
    """Return the default LOCALAPPDATA log directory."""
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "cvcutter" / "logs"
    return Path.home() / "AppData" / "Local" / "cvcutter" / "logs"


def _handler_names() -> set[str]:
    """Return handler names managed by this module."""
    return {_PIPELINE_FILE_HANDLER_NAME, _CONSOLE_HANDLER_NAME}


def _sanitize_project_id(value: str) -> str:
    """Normalize project ID text to a filename-safe value."""
    safe = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)
    return safe or DEFAULT_PROJECT_ID


def _process_metrics() -> tuple[float | None, float | None]:
    """Collect current-process memory and host CPU metrics when psutil is available."""
    try:
        import psutil

        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / (1024**2)
        cpu_percent = psutil.cpu_percent(interval=0.0)
        return memory_mb, cpu_percent
    except Exception:
        return None, None


def _disk_free_gb(path: Path) -> float | None:
    """Collect free disk space at the given path in gigabytes."""
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return usage.free / (1024**3)


def _safe_float(value: float | int | None) -> float | None:
    """Safely normalize numeric telemetry values to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coalesce_metric(primary: float | int | None, fallback: float | None) -> float | None:
    """Use explicit metric value when provided, otherwise fallback to sampled value."""
    resolved_primary = _safe_float(primary)
    if resolved_primary is not None:
        return resolved_primary
    return _safe_float(fallback)

