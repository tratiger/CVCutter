from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from pytest import MonkeyPatch

from cvcutter.application.dto.events import ProcessingEvent
from cvcutter.application.workflows.processing_workflow import ProcessingWorkflow, WorkflowExecutionError
from cvcutter.domain.jobs.processing_job import ProcessingJob


def test_processing_event_envelope_contains_required_fields() -> None:
    event = ProcessingEvent.new(
        event_type="stage.started",
        job_id="job-1",
        payload={"operation": "sync"},
        stage_name="sync",
        attempt=1,
        severity="info",
    )

    UUID(event.event_id)
    assert event.event_schema_version == "1"
    datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00"))
    assert event.job_id == "job-1"
    assert event.stage_name == "sync"
    assert event.attempt == 1


def test_stage_event_requires_job_and_stage_context() -> None:
    with pytest.raises(ValueError):
        ProcessingEvent.new(
            event_type="stage.started",
            job_id=None,
            payload={},
            stage_name="sync",
            attempt=1,
        )
    with pytest.raises(ValueError):
        ProcessingEvent.new(
            event_type="stage.started",
            job_id="job-1",
            payload={},
            stage_name=None,
            attempt=1,
        )


def test_retry_event_requires_positive_attempt() -> None:
    with pytest.raises(ValueError):
        ProcessingEvent.new(
            event_type="retry.scheduled",
            job_id="job-1",
            payload={"reason": "HTTP_429"},
            stage_name="publish",
            attempt=0,
        )


def test_workflow_emits_stage_started_and_completed_events() -> None:
    workflow = ProcessingWorkflow()
    job = ProcessingJob("job-1")
    events = workflow.run_until_complete(job)

    stage_started = [event for event in events if event.event_type == "stage.started"]
    stage_completed = [event for event in events if event.event_type == "stage.completed"]
    assert len(stage_started) == len(job.stages)
    assert len(stage_completed) == len(job.stages)

    for event in events:
        UUID(event.event_id)
        assert event.event_schema_version == "1"
        if event.event_type.startswith(("job.", "stage.", "retry.", "publish.", "cleanup.")):
            assert event.job_id == "job-1"


def test_workflow_marks_job_failed_when_stage_execution_raises(monkeypatch: MonkeyPatch) -> None:
    workflow = ProcessingWorkflow()
    job = ProcessingJob("job-fail")

    def _raise_stage_failure(self: ProcessingJob):
        raise RuntimeError("boom")

    monkeypatch.setattr(ProcessingJob, "complete_current_stage", _raise_stage_failure)

    with pytest.raises(WorkflowExecutionError) as raised:
        workflow.run_until_complete(job)

    assert job.state.value == "failed"
    assert any(event.event_type == "stage.failed" for event in raised.value.events)
    assert any(
        event.event_type == "job.state_changed" and event.payload.get("state") == "failed"
        for event in raised.value.events
    )


def test_workflow_marks_failed_when_stage_index_is_invalid() -> None:
    workflow = ProcessingWorkflow()
    job = ProcessingJob("job-invalid", stage_index=999)

    with pytest.raises(WorkflowExecutionError) as raised:
        workflow.run_until_complete(job)

    assert job.state.value == "failed"
    assert any(event.event_type == "stage.failed" for event in raised.value.events)
    assert any(
        event.event_type == "job.state_changed" and event.payload.get("state") == "failed"
        for event in raised.value.events
    )
