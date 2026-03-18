from cvcutter.application.workflows.processing_workflow import ProcessingWorkflow
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.application.services.resume_service import select_first_incomplete_stage
from cvcutter.domain.jobs.stages import WorkflowStage


def test_resume_from_first_incomplete_stage() -> None:
    completed = [WorkflowStage.INGEST, WorkflowStage.CLASSIFY]
    assert select_first_incomplete_stage(completed) == WorkflowStage.SEGMENT_DETECT


def test_workflow_events_are_isolated_per_run() -> None:
    workflow = ProcessingWorkflow()
    first_id = "11111111-1111-1111-1111-111111111121"
    second_id = "11111111-1111-1111-1111-111111111122"
    first_events = workflow.run_until_complete(ProcessingJob(first_id))
    second_events = workflow.run_until_complete(ProcessingJob(second_id))
    assert first_events is not second_events
    assert all(event.job_id == first_id for event in first_events)
    assert all(event.job_id == second_id for event in second_events)
