from __future__ import annotations

import pytest

from cvcutter.domain.entities.workflow_records import (
    AudioSourceProfile,
    ConfigurationChangeRecord,
    JobDraftLock,
    MediaSegmentCandidate,
    MetadataMappingRecord,
    OperatorRolePolicy,
    PublishingTask,
)


def test_media_segment_candidate_validation_rules() -> None:
    candidate = MediaSegmentCandidate(
        segment_id="seg-1",
        job_id="job-1",
        start_ms=100,
        end_ms=500,
        confidence_score=65,
        requires_review=True,
    )
    assert candidate.review_status == "pending"

    with pytest.raises(ValueError):
        MediaSegmentCandidate(
            segment_id="seg-2",
            job_id="job-1",
            start_ms=500,
            end_ms=100,
            confidence_score=65,
            requires_review=True,
        )


def test_audio_source_profile_validation_rules() -> None:
    profile = AudioSourceProfile(
        audio_profile_id="a-1",
        job_id="job-1",
        source_name="main",
        source_kind="embedded_video",
        offset_ms=0,
    )
    assert profile.tuning_mode == "simple"

    with pytest.raises(ValueError):
        AudioSourceProfile(
            audio_profile_id="a-2",
            job_id="job-1",
            source_name="main",
            source_kind="invalid",
            offset_ms=0,
        )


def test_metadata_mapping_record_validation_rules() -> None:
    mapping = MetadataMappingRecord(
        mapping_id="m-1",
        job_id="job-1",
        segment_id="seg-1",
        schema_version="2",
        title="Track",
        description="desc",
        publish_visibility="public",
    )
    assert mapping.validation_status == "valid"

    with pytest.raises(ValueError):
        MetadataMappingRecord(
            mapping_id="m-2",
            job_id="job-1",
            segment_id="seg-1",
            schema_version="2",
            title="Track",
            description="desc",
            publish_visibility="friends_only",
        )


def test_publishing_task_and_policy_validation_rules() -> None:
    task = PublishingTask(
        publish_task_id="p-1",
        job_id="job-1",
        segment_id="seg-1",
        destination="youtube",
    )
    assert task.status == "pending"

    with pytest.raises(ValueError):
        PublishingTask(
            publish_task_id="p-2",
            job_id="job-1",
            segment_id="seg-1",
            destination="vimeo",
        )

    policy = OperatorRolePolicy(policy_id="r-1", job_id="job-1", context_labels=["editor"])
    assert policy.executable_role == "operator"

    with pytest.raises(ValueError):
        OperatorRolePolicy(policy_id="r-2", job_id="job-1", context_labels=["admin"])


def test_lock_and_config_change_validation_rules() -> None:
    lock = JobDraftLock(
        lock_id="l-1",
        job_id="job-1",
        owner_instance_id="instance",
        owner_display_name="operator",
    )
    assert lock.status == "active"

    change = ConfigurationChangeRecord(
        change_id="c-1",
        job_id="job-1",
        changed_fields=["classification_strategy"],
        dependency_impact=["classify"],
        decision="invalidate_and_continue",
    )
    assert change.decision == "invalidate_and_continue"

    with pytest.raises(ValueError):
        ConfigurationChangeRecord(
            change_id="c-2",
            job_id="job-1",
            changed_fields=["classification_strategy"],
            dependency_impact=["classify"],
            decision="unknown",
        )
