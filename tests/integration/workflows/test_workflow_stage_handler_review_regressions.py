from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from cvcutter.application.workflows.processing_workflow import ProcessingWorkflow
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories



def test_map_metadata_stage_completes_missing_segments_after_partial_write(tmp_path: Path) -> None:
    repo = SqliteRepositories(tmp_path / "partial-mapping.db")
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111195"

    repo.insert_segment("seg-a", job_id, 0, 1000, 90, "pending")
    repo.insert_segment("seg-b", job_id, 1000, 2000, 91, "pending")
    repo.insert_metadata_mapping(
        "map-a",
        job_id,
        "seg-a",
        "2",
        "Track A",
        "",
        [],
        {"source": "preexisting"},
        "public",
        "valid",
    )

    job = ProcessingJob(
        job_id,
        input_video_path=str(tmp_path / "concert.mp4"),
        input_audio_sources=[str(tmp_path / "mic.wav")],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-101",
                    "segment_title": "Track A",
                    "performer_display_name": "Artist A",
                    "publish_visibility": "public",
                },
                {
                    "program_id": "P-102",
                    "segment_title": "Track B",
                    "performer_display_name": "Artist B",
                    "publish_visibility": "public",
                },
            ],
        },
        output_prefs={
            "output_path": str(tmp_path / "out.mp4"),
            "destination": "youtube",
        },
    )

    (tmp_path / "concert.mp4").write_bytes(b"video")
    (tmp_path / "mic.wav").write_bytes(b"audio")

    ProcessingWorkflow(repositories=repo).run_until_complete(job)

    mappings = repo.list_metadata_mappings(job_id)
    mapped_segments = {item[1] for item in mappings}
    assert mapped_segments == {"seg-a", "seg-b"}



def test_runtime_config_source_honors_string_false_and_numeric_duration(tmp_path: Path) -> None:
    repo = SqliteRepositories(tmp_path / "runtime-config-source.db")
    repo.init_schema()

    input_video = tmp_path / "concert.mp4"
    input_video.write_bytes(b"video")
    input_audio = tmp_path / "mic.wav"
    input_audio.write_bytes(b"audio")

    output_file = tmp_path / "exported.mp4"

    job = ProcessingJob(
        "11111111-1111-1111-1111-111111111196",
        input_video_path=str(input_video),
        input_audio_sources=[str(input_audio)],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-201",
                    "segment_title": "Track",
                    "performer_display_name": "Artist",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={
            "output_path": str(output_file),
            "output_format": "mp4",
            "title_overlay_enabled": "false",
            "title_duration_seconds": "7",
            "destination": "youtube",
        },
    )

    ProcessingWorkflow(repositories=repo).run_until_complete(job)

    assert output_file.exists()


def test_sync_stage_backfills_missing_profiles_after_partial_persistence(tmp_path: Path) -> None:
    repo = SqliteRepositories(tmp_path / "sync-backfill.db")
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111197"

    repo.insert_audio_source_profile(
        "existing-embedded",
        job_id,
        "embedded-video-audio",
        "embedded_video",
        0,
        0.0,
        0.0,
        "simple",
        "ok",
        "not_required",
    )

    input_video = tmp_path / "concert.mp4"
    input_video.write_bytes(b"video")
    input_audio = tmp_path / "mic.wav"
    input_audio.write_bytes(b"audio")

    job = ProcessingJob(
        job_id,
        input_video_path=str(input_video),
        input_audio_sources=[str(input_audio)],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-301",
                    "segment_title": "Track",
                    "performer_display_name": "Artist",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={
            "output_path": str(tmp_path / "out.mp4"),
            "destination": "youtube",
        },
    )

    ProcessingWorkflow(repositories=repo).run_until_complete(job)

    profiles = repo.list_audio_source_profiles(job_id)
    source_pairs = {(profile[1], profile[2]) for profile in profiles}
    assert ("embedded-video-audio", "embedded_video") in source_pairs
    assert ("mic.wav", "external") in source_pairs
    assert sum(1 for profile in profiles if profile[1] == "embedded-video-audio" and profile[2] == "embedded_video") == 1


def test_sync_stage_persists_multiple_sources_with_same_basename(tmp_path: Path) -> None:
    repo = SqliteRepositories(tmp_path / "sync-duplicate-names.db")
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111198"

    input_video = tmp_path / "concert.mp4"
    input_video.write_bytes(b"video")
    first_audio = tmp_path / "a" / "mic.wav"
    second_audio = tmp_path / "b" / "mic.wav"
    first_audio.parent.mkdir(parents=True, exist_ok=True)
    second_audio.parent.mkdir(parents=True, exist_ok=True)
    first_audio.write_bytes(b"audio-1")
    second_audio.write_bytes(b"audio-2")

    job = ProcessingJob(
        job_id,
        input_video_path=str(input_video),
        input_audio_sources=[str(first_audio), str(second_audio)],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-401",
                    "segment_title": "Track",
                    "performer_display_name": "Artist",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={"output_path": str(tmp_path / "out.mp4"), "destination": "youtube"},
    )

    ProcessingWorkflow(repositories=repo).run_until_complete(job)

    profiles = repo.list_audio_source_profiles(job_id)
    mic_external_count = sum(1 for profile in profiles if profile[1] == "mic.wav" and profile[2] == "external")
    assert mic_external_count == 2


def test_sync_stage_backfill_handles_partial_state_with_duplicate_basenames(tmp_path: Path) -> None:
    repo = SqliteRepositories(tmp_path / "sync-partial-duplicate-backfill.db")
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111199"

    input_video = tmp_path / "concert.mp4"
    input_video.write_bytes(b"video")
    first_audio = tmp_path / "a" / "mic.wav"
    second_audio = tmp_path / "b" / "mic.wav"
    first_audio.parent.mkdir(parents=True, exist_ok=True)
    second_audio.parent.mkdir(parents=True, exist_ok=True)
    first_audio.write_bytes(b"audio-1")
    second_audio.write_bytes(b"audio-2")

    # Partial persistence: embedded profile and only later duplicate-basename external profile exist.
    repo.insert_audio_source_profile(
        str(uuid5(NAMESPACE_URL, f"{job_id}:audio-profile:embedded_video:embedded-video-audio:1")),
        job_id,
        "embedded-video-audio",
        "embedded_video",
        0,
        0.0,
        0.0,
        "simple",
        "ok",
        "not_required",
    )
    repo.insert_audio_source_profile(
        str(uuid5(NAMESPACE_URL, f"{job_id}:audio-profile:external:mic.wav:2")),
        job_id,
        "mic.wav",
        "external",
        0,
        0.0,
        0.0,
        "simple",
        "ok",
        "not_required",
    )

    job = ProcessingJob(
        job_id,
        input_video_path=str(input_video),
        input_audio_sources=[str(first_audio), str(second_audio)],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-501",
                    "segment_title": "Track",
                    "performer_display_name": "Artist",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={"output_path": str(tmp_path / "out.mp4"), "destination": "youtube"},
    )

    ProcessingWorkflow(repositories=repo).run_until_complete(job)

    profiles = repo.list_audio_source_profiles(job_id)
    assert sum(1 for profile in profiles if profile[1] == "embedded-video-audio" and profile[2] == "embedded_video") == 1
    mic_external_count = sum(1 for profile in profiles if profile[1] == "mic.wav" and profile[2] == "external")
    assert mic_external_count == 2


def test_sync_stage_keeps_source_identity_when_input_order_changes(tmp_path: Path) -> None:
    repo = SqliteRepositories(tmp_path / "sync-order-invariance.db")
    repo.init_schema()
    job_id = "11111111-1111-1111-1111-111111111200"

    input_video = tmp_path / "concert.mp4"
    input_video.write_bytes(b"video")
    first_audio = tmp_path / "a" / "guitar.wav"
    second_audio = tmp_path / "b" / "vocals.wav"
    first_audio.parent.mkdir(parents=True, exist_ok=True)
    second_audio.parent.mkdir(parents=True, exist_ok=True)
    first_audio.write_bytes(b"audio-1")
    second_audio.write_bytes(b"audio-2")

    first_order_job = ProcessingJob(
        job_id,
        input_video_path=str(input_video),
        input_audio_sources=[str(first_audio), str(second_audio)],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-601",
                    "segment_title": "Track",
                    "performer_display_name": "Artist",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={"output_path": str(tmp_path / "out-first.mp4"), "destination": "youtube"},
    )
    ProcessingWorkflow(repositories=repo).run_until_complete(first_order_job)
    first_profiles = repo.list_audio_source_profiles(job_id)
    first_profile_ids = {profile[0] for profile in first_profiles}
    assert first_profile_ids == {
        str(uuid5(NAMESPACE_URL, f"{job_id}:audio-profile:embedded_video:embedded-video-audio:1")),
        str(uuid5(NAMESPACE_URL, f"{job_id}:audio-profile:external:guitar.wav:1")),
        str(uuid5(NAMESPACE_URL, f"{job_id}:audio-profile:external:vocals.wav:1")),
    }

    second_order_job = ProcessingJob(
        job_id,
        active_attempt=2,
        input_video_path=str(input_video),
        input_audio_sources=[str(second_audio), str(first_audio)],
        metadata_source_refs={
            "schema_version": "2",
            "records": [
                {
                    "program_id": "P-602",
                    "segment_title": "Track",
                    "performer_display_name": "Artist",
                    "publish_visibility": "public",
                }
            ],
        },
        output_prefs={"output_path": str(tmp_path / "out-second.mp4"), "destination": "youtube"},
    )
    ProcessingWorkflow(repositories=repo).run_until_complete(second_order_job)
    second_profiles = repo.list_audio_source_profiles(job_id)
    second_profile_ids = {profile[0] for profile in second_profiles}
    assert second_profile_ids == first_profile_ids
