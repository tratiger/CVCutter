from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cvcutter.infrastructure.integrations.adapters import ApprovedAdapters


def test_publish_segment_success_result_has_required_contract_fields(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(state_path=tmp_path / "adapter-idempotency.json")
    result = adapters.publish_segment(
        "seg-1",
        {"destination": "youtube"},
        job_id="job-1",
    )

    assert result.provider == "youtube"
    assert result.operation == "publish_segment"
    assert result.category == "success"
    assert result.terminal
    assert result.idempotency_outcome == "performed"
    assert result.recommended_next_action == "none"
    assert result.external_object_id is not None


def test_publish_segment_rejects_non_approved_destination_as_policy_error(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(state_path=tmp_path / "adapter-idempotency.json")
    result = adapters.publish_segment(
        "seg-1",
        {"destination": "vimeo"},
        job_id="job-1",
    )

    assert result.provider == "youtube"
    assert result.category == "policy"
    assert result.terminal
    assert result.error_code == "destination_not_allowed"
    assert result.idempotency_outcome == "unknown"
    assert result.recommended_next_action == "fix_policy_configuration"


def test_publish_segment_missing_required_fields_returns_blocking_error(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(state_path=tmp_path / "adapter-idempotency.json")
    result = adapters.publish_segment("seg-1", {"title": "Track A"}, job_id="job-1")

    assert result.category == "blocking"
    assert result.terminal
    assert result.error_code == "missing_publish_fields"
    assert result.recommended_next_action == "fix_policy_configuration"


def test_publish_segment_transient_retry_contract_uses_retry_after_when_present(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(state_path=tmp_path / "adapter-idempotency.json")
    result = adapters.publish_segment(
        "seg-1",
        {"destination": "youtube", "simulate_http_429": True},
        job_id="job-1",
    )

    assert result.category == "transient"
    assert not result.terminal
    assert result.error_code == "HTTP_429"
    assert result.retry_after_seconds == 17
    assert result.recommended_next_action == "retry_later"


def test_publish_segment_duplicate_key_is_suppressed_idempotently(tmp_path: Path) -> None:
    state_path = tmp_path / "adapter-idempotency.json"
    first_adapter = ApprovedAdapters(state_path=state_path)
    first = first_adapter.publish_segment("seg-1", {"destination": "youtube"}, job_id="job-1")
    second_adapter = ApprovedAdapters(state_path=state_path)
    second = second_adapter.publish_segment("seg-1", {"destination": "youtube"}, job_id="job-1")

    assert first.idempotency_outcome == "performed"
    assert second.idempotency_outcome == "duplicate_suppressed"
    assert second.category == "success"


def test_publish_segment_dedup_is_atomic_across_concurrent_calls(tmp_path: Path) -> None:
    state_path = tmp_path / "adapter-idempotency.json"

    def _publish_once() -> str:
        result = ApprovedAdapters(state_path=state_path).publish_segment(
            "seg-1",
            {"destination": "youtube"},
            job_id="job-1",
        )
        return result.idempotency_outcome

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result() for future in [executor.submit(_publish_once), executor.submit(_publish_once)]]

    assert sorted(outcomes) == ["duplicate_suppressed", "performed"]


def test_publish_segment_blocks_when_idempotency_store_is_corrupted(tmp_path: Path) -> None:
    state_path = tmp_path / "adapter-idempotency.json"
    state_path.write_text("{malformed", encoding="utf-8")
    result = ApprovedAdapters(state_path=state_path).publish_segment(
        "seg-1",
        {"destination": "youtube"},
        job_id="job-1",
    )
    assert result.category == "blocking"
    assert result.error_code == "idempotency_store_corrupt"


def test_publish_segment_blocks_when_idempotency_store_is_unreadable(tmp_path: Path) -> None:
    unreadable_path = tmp_path / "adapter-idempotency.json"
    unreadable_path.mkdir()
    result = ApprovedAdapters(state_path=unreadable_path).publish_segment(
        "seg-1",
        {"destination": "youtube"},
        job_id="job-1",
    )
    assert result.category == "blocking"
    assert result.error_code == "idempotency_store_unreadable"


def test_publish_segment_blocks_when_idempotency_lock_cannot_be_acquired(tmp_path: Path) -> None:
    blocking_parent = tmp_path / "lock-parent"
    blocking_parent.write_text("not-a-directory", encoding="utf-8")
    state_path = blocking_parent / "adapter-idempotency.json"

    result = ApprovedAdapters(state_path=state_path).publish_segment(
        "seg-1",
        {"destination": "youtube"},
        job_id="job-1",
    )
    assert result.category == "blocking"
    assert result.error_code == "idempotency_store_lock_failed"
