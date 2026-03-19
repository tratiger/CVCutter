from __future__ import annotations

import pytest

from cvcutter.application.workflows.processing_workflow import ProcessingWorkflow, WorkflowExecutionError
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.domain.jobs.stages import WorkflowStage


def test_processing_workflow_persists_checkpoints_and_events(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111151"
    workflow = ProcessingWorkflow(repositories=sqlite_repo)
    job = ProcessingJob(job_id)

    events = workflow.run_until_complete(job)
    checkpoints = sqlite_repo.list_checkpoints(job_id)
    stored_events = sqlite_repo.list_events(job_id)

    assert job.state.value == "completed"
    assert len(events) > 0
    assert len(checkpoints) == len(job.stages)
    assert all(status == "completed" for _, _, status in checkpoints)
    assert any(event_type == "stage.started" for event_type, _, _ in stored_events)
    assert any(event_type == "stage.completed" for event_type, _, _ in stored_events)
    assert sqlite_repo.get_job_state(job_id) == "completed"


def test_processing_workflow_persists_active_attempt_in_events(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111153"
    workflow = ProcessingWorkflow(repositories=sqlite_repo)
    job = ProcessingJob(job_id, active_attempt=2)

    events = workflow.run_until_complete(job)

    stage_events = [event for event in events if event.event_type.startswith("stage.")]
    assert stage_events
    assert all(event.attempt == 2 for event in stage_events)


def test_workflow_resume_uses_persisted_checkpoints(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111154"
    sqlite_repo.insert_checkpoint(job_id, "ingest", 1, "completed")
    sqlite_repo.insert_checkpoint(job_id, "classify", 1, "completed")
    workflow = ProcessingWorkflow(repositories=sqlite_repo)

    resumed_job = ProcessingJob(job_id)
    assert workflow.resume(resumed_job) == "segment_detect"


def test_processing_workflow_persists_failed_checkpoint_on_stage_error(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111152"

    def _raise_on_classify(_job: ProcessingJob) -> None:
        raise RuntimeError("classify failure")

    workflow = ProcessingWorkflow(
        repositories=sqlite_repo,
        stage_handlers={WorkflowStage.CLASSIFY: _raise_on_classify},
    )
    job = ProcessingJob(job_id)

    with pytest.raises(WorkflowExecutionError):
        workflow.run_until_complete(job)

    checkpoints = sqlite_repo.list_checkpoints(job_id)
    assert ("ingest", 1, "completed") in checkpoints
    assert ("classify", 1, "failed") in checkpoints
    assert sqlite_repo.get_job_state(job_id) == "failed"


def test_workflow_keeps_original_error_when_failed_checkpoint_insert_conflicts(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111155"
    sqlite_repo.insert_checkpoint(job_id, "classify", 1, "failed")

    def _raise_on_classify(_job: ProcessingJob) -> None:
        raise RuntimeError("classify failure")

    workflow = ProcessingWorkflow(
        repositories=sqlite_repo,
        stage_handlers={WorkflowStage.CLASSIFY: _raise_on_classify},
    )
    job = ProcessingJob(job_id)

    with pytest.raises(WorkflowExecutionError) as raised:
        workflow.run_until_complete(job)
    assert "classify failure" in str(raised.value)


def test_workflow_checkpoint_persistence_failure_does_not_mask_with_state_error(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111156"

    def _checkpoint_already_exists(_job: ProcessingJob) -> None:
        sqlite_repo.insert_checkpoint(job_id, "ingest", 1, "completed")

    workflow = ProcessingWorkflow(
        repositories=sqlite_repo,
        stage_handlers={WorkflowStage.INGEST: _checkpoint_already_exists},
    )
    job = ProcessingJob(job_id)

    with pytest.raises(WorkflowExecutionError) as raised:
        workflow.run_until_complete(job)
    assert "UNIQUE constraint failed" in str(raised.value)


def test_workflow_does_not_persist_completed_when_final_checkpoint_write_fails(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111157"
    sqlite_repo.insert_checkpoint(job_id, "publish", 1, "completed")

    workflow = ProcessingWorkflow(repositories=sqlite_repo)
    job = ProcessingJob(job_id)

    with pytest.raises(WorkflowExecutionError):
        workflow.run_until_complete(job)

    assert sqlite_repo.get_job_state(job_id) == "failed"
