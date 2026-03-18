import pytest

from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.domain.jobs.stages import JobState, WorkflowStage


def test_processing_job_lifecycle_transitions() -> None:
    job = ProcessingJob("j1")
    assert [stage.value for stage in job.stages] == [
        "ingest",
        "classify",
        "segment_detect",
        "sync",
        "map_metadata",
        "export",
        "publish",
    ]
    job.start()
    assert job.state == JobState.RUNNING
    while job.state == JobState.RUNNING:
        job.complete_current_stage()
    assert job.state == JobState.COMPLETED


def test_non_operator_role_blocked() -> None:
    job = ProcessingJob("j2", role="editor")
    with pytest.raises(PermissionError):
        job.start()


def test_completed_job_cannot_restart() -> None:
    job = ProcessingJob("j3")
    job.start()
    while job.state == JobState.RUNNING:
        job.complete_current_stage()
    with pytest.raises(RuntimeError):
        job.start()


def test_completed_job_cannot_fail_or_cancel() -> None:
    job = ProcessingJob("j4")
    job.start()
    while job.state == JobState.RUNNING:
        job.complete_current_stage()
    with pytest.raises(RuntimeError):
        job.fail()
    with pytest.raises(RuntimeError):
        job.cancel()


def test_running_job_can_cancel() -> None:
    job = ProcessingJob("j5")
    job.start()
    job.cancel()
    assert job.state == JobState.CANCELED


def test_workflow_stage_enum_uses_only_canonical_members() -> None:
    assert not hasattr(WorkflowStage, "SEGMENT")
    assert not hasattr(WorkflowStage, "MAP")
