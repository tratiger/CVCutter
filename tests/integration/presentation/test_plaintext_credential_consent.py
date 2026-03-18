from pathlib import Path

import pytest

from cvcutter.presentation.flet_app.viewmodels.publish_workflow_viewmodel import PublishWorkflowViewModel


def test_plaintext_credential_consent_gate(tmp_path: Path) -> None:
    credentials_path = tmp_path / "plaintext-credentials.json"
    vm = PublishWorkflowViewModel(consent_given=False, credentials_path=credentials_path)
    assert not vm.can_save_plaintext_credentials()
    assert not vm.save_plaintext_credentials({"token": "x"})
    assert not credentials_path.exists()

    vm.consent_given = True
    assert vm.can_save_plaintext_credentials()
    assert vm.save_plaintext_credentials({"token": "x"})
    assert credentials_path.exists()
    assert vm.load_plaintext_credentials()["token"] == "x"

    reloaded = PublishWorkflowViewModel(consent_given=True, credentials_path=credentials_path)
    assert reloaded.load_plaintext_credentials()["token"] == "x"


def test_plaintext_credential_default_path_uses_user_config_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    vm = PublishWorkflowViewModel(consent_given=True)
    assert vm.credentials_path == tmp_path / "CVCutter" / "plaintext-credentials.json"


def test_plaintext_credential_load_rejects_malformed_payload(tmp_path: Path) -> None:
    credentials_path = tmp_path / "plaintext-credentials.json"
    credentials_path.write_text("{bad-json", encoding="utf-8")
    vm = PublishWorkflowViewModel(consent_given=True, credentials_path=credentials_path)

    with pytest.raises(ValueError, match="invalid_plaintext_credential_payload"):
        vm.load_plaintext_credentials()
