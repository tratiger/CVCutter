from cvcutter.application.workflows.processing_workflow import ProcessingWorkflow
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.application.services.resume_service import select_first_incomplete_stage
from cvcutter.domain.jobs.stages import WorkflowStage


def test_resume_from_first_incomplete_stage() -> None:
    completed = [WorkflowStage.INGEST, WorkflowStage.SEGMENT]
    assert select_first_incomplete_stage(completed) == WorkflowStage.SYNC


def test_workflow_events_are_isolated_per_run() -> None:
    workflow = ProcessingWorkflow()
    first_events = workflow.run_until_complete(ProcessingJob("job-1"))
    second_events = workflow.run_until_complete(ProcessingJob("job-2"))
    assert first_events is not second_events
    assert all(event.job_id == "job-1" for event in first_events)
    assert all(event.job_id == "job-2" for event in second_events)
