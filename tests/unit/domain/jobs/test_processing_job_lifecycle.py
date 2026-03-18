import pytest

from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.domain.jobs.stages import JobState, WorkflowStage


def _uuid(last_char: str) -> str:
    return f"11111111-1111-1111-1111-11111111111{last_char}"


def test_processing_job_lifecycle_transitions() -> None:
    job = ProcessingJob(_uuid("1"))
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
    job = ProcessingJob(_uuid("2"), role="editor")
    with pytest.raises(PermissionError):
        job.start()


def test_completed_job_cannot_restart() -> None:
    job = ProcessingJob(_uuid("3"))
    job.start()
    while job.state == JobState.RUNNING:
        job.complete_current_stage()
    with pytest.raises(RuntimeError):
        job.start()


def test_completed_job_cannot_fail_or_cancel() -> None:
    job = ProcessingJob(_uuid("4"))
    job.start()
    while job.state == JobState.RUNNING:
        job.complete_current_stage()
    with pytest.raises(RuntimeError):
        job.fail()
    with pytest.raises(RuntimeError):
        job.cancel()


def test_running_job_can_cancel() -> None:
    job = ProcessingJob(_uuid("5"))
    job.start()
    job.cancel()
    assert job.state == JobState.CANCELED


def test_paused_or_resumable_job_cannot_fail_or_cancel() -> None:
    job = ProcessingJob(_uuid("6"))
    job.start()
    job.pause()
    with pytest.raises(RuntimeError):
        job.fail()
    with pytest.raises(RuntimeError):
        job.cancel()

    job.mark_resumable()
    with pytest.raises(RuntimeError):
        job.fail()
    with pytest.raises(RuntimeError):
        job.cancel()


def test_paused_job_cannot_restart_without_resumable_transition() -> None:
    job = ProcessingJob(_uuid("7"))
    job.start()
    job.pause()
    with pytest.raises(RuntimeError, match="mark job resumable first"):
        job.start()
    job.mark_resumable()
    job.start()
    assert job.state == JobState.RUNNING


def test_job_id_must_be_uuid_and_immutable() -> None:
    with pytest.raises(ValueError, match="valid UUID"):
        ProcessingJob("not-a-uuid")

    job = ProcessingJob(_uuid("8"))
    with pytest.raises(AttributeError, match="immutable"):
        job.job_id = _uuid("9")


def test_workflow_stage_enum_uses_only_canonical_members() -> None:
    assert not hasattr(WorkflowStage, "SEGMENT")
    assert not hasattr(WorkflowStage, "MAP")
