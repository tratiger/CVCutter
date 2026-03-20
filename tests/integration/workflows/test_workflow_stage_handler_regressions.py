from __future__ import annotations

import json
from pathlib import Path

from cvcutter.application.workflows.processing_workflow import ProcessingWorkflow
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories



def test_sync_stage_uses_effective_source_count_for_sync_path(tmp_path: Path) -> None:
    repo = SqliteRepositories(tmp_path / "sync-path.db")
    repo.init_schema()

    (tmp_path / "concert.mp4").write_bytes(b"video")
    (tmp_path / "mic.wav").write_bytes(b"audio")

    job = ProcessingJob(
        "11111111-1111-1111-1111-111111111193",
        input_video_path=str(tmp_path / "concert.mp4"),
        input_audio_sources=[str(tmp_path / "mic.wav")],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-002",
                    "segment_title": "Main",
                    "performer_display_name": "Artist",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={"output_path": str(tmp_path / "out.mp4"), "destination": "youtube"},
    )

    ProcessingWorkflow(repositories=repo).run_until_complete(job)

    sync_events = [
        json.loads(payload)
        for event_type, _job_id, payload in repo.list_events(job.job_id)
        if event_type == "sync.path_selected"
    ]
    assert sync_events
    assert sync_events[0]["payload"]["source_count"] >= 2
    assert sync_events[0]["payload"]["sync_path"] == "manual_sync"



def test_export_stage_accepts_output_directory_path(tmp_path: Path) -> None:
    repo = SqliteRepositories(tmp_path / "export-dir.db")
    repo.init_schema()

    (tmp_path / "concert.mp4").write_bytes(b"video")
    (tmp_path / "mic.wav").write_bytes(b"audio")

    output_dir = tmp_path / "exports"

    job = ProcessingJob(
        "11111111-1111-1111-1111-111111111194",
        input_video_path=str(tmp_path / "concert.mp4"),
        input_audio_sources=[str(tmp_path / "mic.wav")],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-003",
                    "segment_title": "Finale",
                    "performer_display_name": "Artist",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={
            "output_path": str(output_dir),
            "output_format": "mp4",
            "destination": "youtube",
        },
    )

    ProcessingWorkflow(repositories=repo).run_until_complete(job)

    export_events = [
        json.loads(payload)
        for event_type, _job_id, payload in repo.list_events(job.job_id)
        if event_type == "export.completed"
    ]
    assert export_events
    exported_path = Path(str(export_events[0]["payload"]["output_path"]))
    assert exported_path.suffix == ".mp4"
    assert exported_path.parent == output_dir
