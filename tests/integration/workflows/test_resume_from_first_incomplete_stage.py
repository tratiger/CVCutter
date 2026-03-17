from cvcutter.application.services.resume_service import select_first_incomplete_stage
from cvcutter.domain.jobs.stages import WorkflowStage


def test_resume_from_first_incomplete_stage() -> None:
    completed = [WorkflowStage.INGEST, WorkflowStage.SEGMENT]
    assert select_first_incomplete_stage(completed) == WorkflowStage.SYNC
