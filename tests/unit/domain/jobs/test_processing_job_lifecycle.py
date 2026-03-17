import pytest

from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.domain.jobs.stages import JobState


def test_processing_job_lifecycle_transitions() -> None:
    job = ProcessingJob("j1")
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
