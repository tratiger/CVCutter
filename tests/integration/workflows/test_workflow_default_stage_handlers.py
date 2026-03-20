from __future__ import annotations

import json
from pathlib import Path

from cvcutter.application.workflows.processing_workflow import ProcessingWorkflow
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


def _build_job(job_id: str, tmp_path: Path) -> ProcessingJob:
    return ProcessingJob(
        job_id,
        classification_strategy="content_based",
        low_confidence_threshold=70,
        input_video_path=str(tmp_path / "concert.mp4"),
        input_audio_sources=[str(tmp_path / "concert.wav")],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-001",
                    "segment_title": "Opening",
                    "performer_display_name": "Artist A",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={
            "output_path": str(tmp_path / "outputs"),
            "output_format": "mp4",
            "title_overlay_enabled": False,
            "title_duration_seconds": 0,
            "destination": "youtube",
        },
    )


def test_workflow_default_handlers_persist_stage_side_effects(tmp_path: Path) -> None:
    db_path = tmp_path / "workflow-default-handlers.db"
    repo = SqliteRepositories(db_path)
    repo.init_schema()

    input_video = tmp_path / "concert.mp4"
    input_video.write_bytes(b"video-bytes")
    input_audio = tmp_path / "concert.wav"
    input_audio.write_bytes(b"audio-bytes")

    workflow = ProcessingWorkflow(repositories=repo)
    job_id = "11111111-1111-1111-1111-111111111191"
    job = _build_job(job_id, tmp_path)
    events = workflow.run_until_complete(job)

    assert job.state.value == "completed"
    assert any(event.event_type == "stage.completed" and event.stage_name == "publish" for event in events)

    stored_events = [json.loads(payload) for event_type, _job_id, payload in repo.list_events(job_id) if event_type == "stage.completed"]
    stage_names = {item.get("stage_name") for item in stored_events}
    assert {"ingest", "classify", "segment_detect", "sync", "map_metadata", "export", "publish"}.issubset(stage_names)

    mappings = repo.list_metadata_mappings(job_id)
    assert mappings
    assert mappings[0][1]
    assert mappings[0][2] == "2"



def test_workflow_default_publish_stage_records_publish_event(tmp_path: Path) -> None:
    db_path = tmp_path / "workflow-default-publish.db"
    repo = SqliteRepositories(db_path)
    repo.init_schema()

    input_video = tmp_path / "concert.mp4"
    input_video.write_bytes(b"video-bytes")
    input_audio = tmp_path / "concert.wav"
    input_audio.write_bytes(b"audio-bytes")

    workflow = ProcessingWorkflow(repositories=repo)
    job_id = "11111111-1111-1111-1111-111111111192"
    workflow.run_until_complete(_build_job(job_id, tmp_path))

    publish_events = [
        (event_type, json.loads(payload))
        for event_type, _event_job_id, payload in repo.list_events(job_id)
        if event_type.startswith("publish.")
    ]
    assert publish_events
    assert any(
        isinstance(payload.get("payload"), dict) and payload["payload"].get("operation") == "publish_segment"
        for _, payload in publish_events
    )
    export_events = [
        json.loads(payload)
        for event_type, _event_job_id, payload in repo.list_events(job_id)
        if event_type == "export.completed"
    ]
    assert export_events
    assert str(export_events[0]["payload"]["output_path"]).endswith(".mp4")
