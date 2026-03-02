"""Unit tests for structured JSON logging infrastructure.

These tests lock down baseline observability requirements for Phase 2:
JSON schema presence, parseability, logging bootstrap behavior, and
stage-transition event payload shape.
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import pytest

from cvcutter.infrastructure.logging.structured_logger import (
    JsonFormatter,
    init_logging,
    log_resource_telemetry,
    log_stage_transition,
)


@pytest.fixture
def restore_root_logger():
    """Restore root-logger handlers/level after each test touching global logging."""
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    try:
        yield
    finally:
        current_handlers = list(root_logger.handlers)
        for handler in current_handlers:
            if handler not in original_handlers:
                handler.close()
        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)


def test_json_log_format_has_required_fields() -> None:
    """Formatted JSON logs should include required foundational schema fields."""
    record = logging.LogRecord(
        name="tests.structured_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="pipeline started",
        args=(),
        exc_info=None,
    )
    record.operation_id = "op-123"
    record.pipeline_stage = "DETECTION"

    payload = json.loads(JsonFormatter().format(record))

    assert {"timestamp", "level", "operation_id", "pipeline_stage"} <= payload.keys()
    assert payload["operation_id"] == "op-123"
    assert payload["pipeline_stage"] == "DETECTION"


def test_log_entries_are_valid_json() -> None:
    """Each formatted log entry should be parseable JSON."""
    formatter = JsonFormatter()

    record = logging.LogRecord(
        name="tests.structured_logger",
        level=logging.WARNING,
        pathname=__file__,
        lineno=2,
        msg="warning event",
        args=(),
        exc_info=None,
    )
    rendered = formatter.format(record)
    parsed = json.loads(rendered)

    assert isinstance(parsed, dict)
    assert parsed["message"] == "warning event"
    assert parsed["level"] == "WARNING"


def test_init_logging_creates_file_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_root_logger: None,
) -> None:
    """Logging initialization should attach the pipeline JSON file handler."""
    monkeypatch.setenv("CVCUTTER_PROJECT_ID", "phase2")

    init_logging(log_dir=tmp_path)
    root_logger = logging.getLogger()
    file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
    pipeline_handlers = [h for h in file_handlers if h.name == "cvcutter.pipeline_jsonl"]

    assert len(pipeline_handlers) == 1
    assert Path(pipeline_handlers[0].baseFilename) == tmp_path / "pipeline_phase2.jsonl"


def test_init_logging_sanitizes_project_id_for_log_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_root_logger: None,
) -> None:
    """Project ID from environment should be sanitized into a safe log filename."""
    monkeypatch.setenv("CVCUTTER_PROJECT_ID", "..\\..\\unsafe")

    init_logging(log_dir=tmp_path)
    root_logger = logging.getLogger()
    file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
    pipeline_handler = next(h for h in file_handlers if h.name == "cvcutter.pipeline_jsonl")

    base_path = Path(pipeline_handler.baseFilename)
    assert base_path.parent == tmp_path
    assert ".." not in base_path.name


def test_log_stage_transition_helper_produces_expected_event_structure() -> None:
    """Stage-transition helper should emit a structured event payload."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("tests.structured_logger.transition")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        log_stage_transition(
            logger,
            stage="EXPORT",
            event="completed",
            checkpoint_id="ckpt-001",
            input_refs=["segment-01.mp4"],
            output_refs=["exported-01.mp4"],
            decision="proceed",
            decision_reason="validation-passed",
            duration_ms=123.4,
            operation_id="op-xyz",
        )
    finally:
        logger.handlers = []
        logger.propagate = True

    payload = json.loads(stream.getvalue().strip())
    assert payload["pipeline_stage"] == "EXPORT"
    assert payload["event"] == "completed"
    assert payload["checkpoint_id"] == "ckpt-001"
    assert payload["operation_id"] == "op-xyz"
    assert payload["input_refs"] == ["segment-01.mp4"]
    assert payload["output_refs"] == ["exported-01.mp4"]
    assert payload["decision"] == "proceed"
    assert payload["decision_reason"] == "validation-passed"
    assert payload["duration_ms"] == 123.4


def test_log_resource_telemetry_emits_resource_fields() -> None:
    """Resource telemetry helper should populate memory/disk/cpu fields."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("tests.structured_logger.telemetry")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        log_resource_telemetry(
            logger,
            stage="EXPORT",
            operation_id="op-telemetry",
            memory_mb=123.4,
            disk_free_gb=456.7,
            cpu_percent=12.5,
        )
    finally:
        logger.handlers = []
        logger.propagate = True

    payload = json.loads(stream.getvalue().strip())
    assert payload["event"] == "RESOURCE_TELEMETRY"
    assert payload["pipeline_stage"] == "EXPORT"
    assert payload["operation_id"] == "op-telemetry"
    assert payload["memory_mb"] == 123.4
    assert payload["disk_free_gb"] == 456.7
    assert payload["cpu_percent"] == 12.5
