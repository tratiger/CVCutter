from __future__ import annotations

from pathlib import Path

from cvcutter.infrastructure.integrations.adapters import ApprovedAdapters


JOB_ID = "11111111-1111-1111-1111-111111111111"



def test_fetch_form_responses_rejects_empty_form_id(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(state_path=tmp_path / "adapter-idempotency.json")
    result = adapters.fetch_form_responses("  ", job_id=JOB_ID)

    assert result.category == "blocking"
    assert result.error_code == "missing_form_id"
    assert result.recommended_next_action == "fix_policy_configuration"



def test_fetch_form_responses_returns_normalized_records_payload(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(state_path=tmp_path / "adapter-idempotency.json")
    result = adapters.fetch_form_responses("form-abc", job_id=JOB_ID)

    assert result.category == "success"
    assert result.external_object_id is not None
    assert result.external_object_id.startswith("gf:")
    assert "form-abc" not in result.external_object_id
    payload = result.payload
    assert "form-abc" not in str(payload)
    assert isinstance(payload["records"], list)
    assert payload["records"]
    first = payload["records"][0]
    assert first["program_id"] == "P-AUTO-IMPORTED"
    assert first["segment_title"]
    assert first["performer_display_name"]
    assert first["publish_visibility"] in {"public", "unlisted", "private"}



def test_classify_content_blocks_on_empty_text(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(state_path=tmp_path / "adapter-idempotency.json")
    result = adapters.classify_content("   ", job_id=JOB_ID)

    assert result.category == "blocking"
    assert result.error_code == "empty_content"



def test_classify_content_returns_non_content_reference_id(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(state_path=tmp_path / "adapter-idempotency.json")
    text = "Encore performance with piano and violin"
    result = adapters.classify_content(text, job_id=JOB_ID)

    assert result.category == "success"
    assert result.external_object_id is None
    reference_id = str(result.payload["classification_reference_id"])
    assert reference_id.startswith("cls:")
    assert "Encore performance" not in reference_id
    assert text not in reference_id


class _BrokenFormsClient:
    def fetch(self, form_id: str, *, job_id: str) -> dict[str, object]:
        return {"schema_version": "2", "source_format": "json", "records": []}


class _CustomClassifierClient:
    def classify(self, text: str, *, job_id: str) -> dict[str, object]:
        return {
            "classification_reference_id": "custom-ref-id",
            "top_candidate": "encore",
            "confidence_state": "confident",
        }


class _RaisingFormsClient:
    def fetch(self, form_id: str, *, job_id: str) -> dict[str, object]:
        raise RuntimeError("provider down")


class _RaisingClassifierClient:
    def classify(self, text: str, *, job_id: str) -> dict[str, object]:
        raise RuntimeError("provider down")


class _UnsafeClassifierClient:
    def classify(self, text: str, *, job_id: str) -> dict[str, object]:
        return {
            "classification_reference_id": "SSN 123-45-6789 private note",
            "top_candidate": "encore",
            "confidence_state": "confident",
        }


class _InvalidRecordFormsClient:
    def fetch(self, form_id: str, *, job_id: str) -> dict[str, object]:
        return {
            "schema_version": "2",
            "source_format": "json",
            "records": [
                {
                    "program_id": "",
                    "segment_title": "",
                    "performer_display_name": "",
                    "publish_visibility": "friends-only",
                }
            ],
        }


def test_fetch_form_responses_blocks_on_invalid_provider_payload(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(
        state_path=tmp_path / "adapter-idempotency.json",
        forms_client=_BrokenFormsClient(),
    )
    result = adapters.fetch_form_responses("form-abc", job_id=JOB_ID)

    assert result.category == "blocking"
    assert result.error_code == "invalid_form_payload"


def test_classify_content_normalizes_provider_reference_identifier(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(
        state_path=tmp_path / "adapter-idempotency.json",
        classifier_client=_CustomClassifierClient(),
    )
    result = adapters.classify_content("encore section", job_id=JOB_ID)

    assert result.category == "success"
    reference_id = str(result.payload["classification_reference_id"])
    assert reference_id.startswith("cls:")
    assert "custom-ref-id" not in reference_id


def test_fetch_form_responses_returns_transient_result_on_provider_exception(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(
        state_path=tmp_path / "adapter-idempotency.json",
        forms_client=_RaisingFormsClient(),
    )
    result = adapters.fetch_form_responses("form-abc", job_id=JOB_ID)

    assert result.category == "transient"
    assert result.error_code == "forms_provider_unavailable"


def test_classify_content_returns_transient_result_on_provider_exception(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(
        state_path=tmp_path / "adapter-idempotency.json",
        classifier_client=_RaisingClassifierClient(),
    )
    result = adapters.classify_content("encore section", job_id=JOB_ID)

    assert result.category == "transient"
    assert result.error_code == "classification_provider_unavailable"


def test_classify_content_sanitizes_unsafe_reference_identifier(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(
        state_path=tmp_path / "adapter-idempotency.json",
        classifier_client=_UnsafeClassifierClient(),
    )
    result = adapters.classify_content("encore section", job_id=JOB_ID)

    assert result.category == "success"
    reference_id = str(result.payload["classification_reference_id"])
    assert reference_id.startswith("cls:")
    assert "SSN" not in reference_id
    assert "private note" not in reference_id


def test_classify_content_keeps_safe_prefixed_reference_identifier(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(state_path=tmp_path / "adapter-idempotency.json")
    result = adapters.classify_content("encore section", job_id=JOB_ID)

    assert result.category == "success"
    reference_id = str(result.payload["classification_reference_id"])
    assert reference_id.startswith("cls:")
    assert len(reference_id) == len("cls:") + 40


def test_fetch_form_responses_blocks_when_provider_records_fail_contract(tmp_path: Path) -> None:
    adapters = ApprovedAdapters(
        state_path=tmp_path / "adapter-idempotency.json",
        forms_client=_InvalidRecordFormsClient(),
    )
    result = adapters.fetch_form_responses("form-abc", job_id=JOB_ID)

    assert result.category == "blocking"
    assert result.error_code == "invalid_form_payload"
