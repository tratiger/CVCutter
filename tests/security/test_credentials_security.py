"""Security checks for credential storage and redaction behavior (T108)."""

from __future__ import annotations

import io
import json
import logging
import os
import stat
from pathlib import Path

import pytest

import cvcutter.infrastructure.persistence.json_credential_store as credential_store_module
from cvcutter.infrastructure.logging.structured_logger import JsonFormatter
from cvcutter.infrastructure.persistence.json_credential_store import JsonCredentialStore

pytestmark = pytest.mark.security


@pytest.fixture
def credentials_payload() -> dict[str, str]:
    return {
        "access_token": "token-secret-access",
        "refresh_token": "token-secret-refresh",
    }


def test_credentials_are_saved_with_restricted_file_permissions(
    tmp_path: Path,
    credentials_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _capture_chmod(path: str | os.PathLike[str], mode: int) -> None:
        captured["path"] = Path(path)
        captured["mode"] = mode

    monkeypatch.setattr(credential_store_module.os, "chmod", _capture_chmod)
    store = JsonCredentialStore(tmp_path)
    store.save("youtube", credentials_payload)

    credential_path = tmp_path / "credentials" / "youtube.json"
    expected_mode = (
        stat.S_IREAD | stat.S_IWRITE
        if os.name == "nt"
        else stat.S_IRUSR | stat.S_IWUSR
    )
    assert credential_path.exists()
    assert captured["path"] == credential_path
    assert captured["mode"] == expected_mode


def test_credential_redaction_is_used_for_logs_and_diagnostics(
    tmp_path: Path,
    credentials_payload: dict[str, str],
) -> None:
    store = JsonCredentialStore(tmp_path)
    store.save("youtube", credentials_payload)
    redacted = store.redacted_summary("youtube")
    diagnostics_json = json.dumps({"credentials": redacted}, ensure_ascii=False)

    assert redacted == {"access_token": "***", "refresh_token": "***"}
    assert credentials_payload["access_token"] not in diagnostics_json
    assert credentials_payload["refresh_token"] not in diagnostics_json


def test_structured_log_output_does_not_leak_raw_credentials() -> None:
    secret_value = "super-secret-token"
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("tests.security.credentials_security")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        logger.info(
            "credential diagnostics",
            extra={
                "operation_id": "op-security",
                "pipeline_stage": "SETTINGS",
                "checkpoint_id": "ckpt-security",
                "event": "CREDENTIAL_DIAGNOSTICS",
                "decision": "redacted",
                "decision_reason": "summary_only",
                "output_refs": ['{"access_token":"***","refresh_token":"***"}'],
                "raw_credentials": {"access_token": secret_value},
            },
        )
    finally:
        handler.close()
        logger.handlers = []
        logger.propagate = True

    payload_text = stream.getvalue().strip()
    payload = json.loads(payload_text)

    assert "raw_credentials" not in payload
    assert secret_value not in payload_text
    assert payload["checkpoint_id"] == "ckpt-security"
