from __future__ import annotations

import pytest

from cvcutter.application.workflows.processing_workflow import ProcessingWorkflow, WorkflowExecutionError
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.domain.jobs.stages import WorkflowStage
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


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
    detailed_events = sqlite_repo.list_events_detailed(job_id)
    assert any(event["event_type"] == "stage.started" and event["is_minimal_audit"] for event in detailed_events)
    assert any(event["event_type"] == "stage.completed" and event["is_minimal_audit"] for event in detailed_events)
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


def test_workflow_resume_understands_legacy_stage_aliases(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111158"
    sqlite_repo.insert_checkpoint(job_id, "ingest", 1, "completed")
    sqlite_repo.insert_checkpoint(job_id, "classify", 1, "completed")
    sqlite_repo.insert_checkpoint(job_id, "segment", 1, "completed")
    workflow = ProcessingWorkflow(repositories=sqlite_repo)

    resumed_job = ProcessingJob(job_id)
    assert workflow.resume(resumed_job) == "sync"


def test_workflow_resume_understands_legacy_alias_after_schema_migration(tmp_path) -> None:
    import sqlite3

    db_path = tmp_path / "legacy-checkpoint.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE checkpoints (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO checkpoints(id, job_id, stage, status, created_at) VALUES
                ('legacy-1', '11111111-1111-1111-1111-111111111159', 'ingest', 'completed', '2024-01-01T00:00:00Z'),
                ('legacy-2', '11111111-1111-1111-1111-111111111159', 'classify', 'completed', '2024-01-01T00:00:01Z'),
                ('legacy-3', '11111111-1111-1111-1111-111111111159', 'segment', 'completed', '2024-01-01T00:00:02Z');
            """
        )
        conn.commit()
    finally:
        conn.close()

    repo = SqliteRepositories(db_path)
    repo.init_schema()
    workflow = ProcessingWorkflow(repositories=repo)
    resumed_job = ProcessingJob("11111111-1111-1111-1111-111111111159")
    assert workflow.resume(resumed_job) == "sync"


def test_workflow_resume_executes_remaining_stages_and_persists_state(sqlite_repo, tmp_path) -> None:
    job_id = "11111111-1111-1111-1111-111111111177"
    sqlite_repo.insert_checkpoint(job_id, "ingest", 2, "completed")
    sqlite_repo.insert_checkpoint(job_id, "classify", 2, "completed")
    sqlite_repo.insert_checkpoint(job_id, "segment_detect", 2, "completed")

    input_video = tmp_path / "concert.mp4"
    input_audio = tmp_path / "mic.wav"
    input_video.write_bytes(b"video")
    input_audio.write_bytes(b"audio")

    resumed_job = ProcessingJob(
        job_id,
        active_attempt=2,
        input_video_path=str(input_video),
        input_audio_sources=[str(input_audio)],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-701",
                    "segment_title": "Track",
                    "performer_display_name": "Artist",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={"output_path": str(tmp_path / "out.mp4"), "destination": "youtube"},
    )

    workflow = ProcessingWorkflow(repositories=sqlite_repo)
    resume_stage = workflow.resume(resumed_job)
    assert resume_stage == "sync"
    assert resumed_job.state.value == "completed"
    checkpoints = sqlite_repo.list_checkpoints(job_id)
    assert ("sync", 2, "completed") in checkpoints
    assert ("map_metadata", 2, "completed") in checkpoints
    assert ("export", 2, "completed") in checkpoints
    assert ("publish", 2, "completed") in checkpoints
    assert sqlite_repo.get_job_state(job_id) == "completed"


def test_workflow_resume_marks_completed_when_no_remaining_stage(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111178"
    for stage in ("ingest", "classify", "segment_detect", "sync", "map_metadata", "export", "publish"):
        sqlite_repo.insert_checkpoint(job_id, stage, 1, "completed")

    job = ProcessingJob(job_id)
    workflow = ProcessingWorkflow(repositories=sqlite_repo)
    result = workflow.resume(job)

    assert result == "done"
    assert job.state.value == "completed"
    assert job.ended_at is not None
    assert sqlite_repo.get_job_state(job_id) == "completed"


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


def test_workflow_heartbeat_updates_active_job_lock(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111160"
    assert sqlite_repo.acquire_active_job_lock(job_id)
    conn = sqlite_repo.connect()
    try:
        conn.execute(
            "UPDATE locks SET heartbeat_at = datetime('now', '-1000 seconds') WHERE lock_name = 'active_job'"
        )
        conn.commit()
    finally:
        conn.close()

    workflow = ProcessingWorkflow(repositories=sqlite_repo)
    workflow.run_until_complete(ProcessingJob(job_id))
    lock_info = sqlite_repo.get_active_job_lock_info()
    assert lock_info is not None
    owner, heartbeat_age = lock_info
    assert owner == job_id
    assert heartbeat_age < 30


def test_workflow_marks_failed_when_heartbeat_init_fails(sqlite_repo, monkeypatch) -> None:
    job_id = "11111111-1111-1111-1111-111111111175"
    workflow = ProcessingWorkflow(repositories=sqlite_repo)

    def _raise_heartbeat(*_args, **_kwargs):
        raise RuntimeError("heartbeat-failed")

    monkeypatch.setattr(
        "cvcutter.infrastructure.persistence.repositories.SqliteRepositories.touch_active_job_lock",
        _raise_heartbeat,
    )
    with pytest.raises(WorkflowExecutionError) as raised:
        workflow.run_until_complete(ProcessingJob(job_id))
    assert "heartbeat-failed" in str(raised.value)
    assert sqlite_repo.get_job_state(job_id) == "failed"


def test_workflow_marks_failed_when_heartbeat_thread_fails(sqlite_repo, monkeypatch) -> None:
    job_id = "11111111-1111-1111-1111-111111111176"
    workflow = ProcessingWorkflow(repositories=sqlite_repo)
    original_touch = SqliteRepositories.touch_active_job_lock
    state = {"calls": 0}

    def _flaky_touch(self: SqliteRepositories, active_job_id: str) -> None:
        state["calls"] += 1
        if state["calls"] == 1:
            original_touch(self, active_job_id)
            return
        raise RuntimeError("heartbeat-thread-failed")

    monkeypatch.setattr(SqliteRepositories, "touch_active_job_lock", _flaky_touch)

    def _slow_classify(_job: ProcessingJob) -> None:
        import time

        time.sleep(2.5)

    workflow.stage_handlers = {WorkflowStage.CLASSIFY: _slow_classify}
    with pytest.raises(WorkflowExecutionError) as raised:
        workflow.run_until_complete(ProcessingJob(job_id))
    assert "heartbeat-thread-failed" in str(raised.value)
    assert sqlite_repo.get_job_state(job_id) == "failed"


def test_workflow_does_not_persist_completed_when_final_checkpoint_write_fails(sqlite_repo) -> None:
    job_id = "11111111-1111-1111-1111-111111111157"
    sqlite_repo.insert_checkpoint(job_id, "publish", 1, "completed")

    workflow = ProcessingWorkflow(repositories=sqlite_repo)
    job = ProcessingJob(job_id)

    with pytest.raises(WorkflowExecutionError):
        workflow.run_until_complete(job)

    assert sqlite_repo.get_job_state(job_id) == "failed"
