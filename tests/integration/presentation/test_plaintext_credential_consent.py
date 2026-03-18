from cvcutter.presentation.flet_app.viewmodels.publish_workflow_viewmodel import PublishWorkflowViewModel


def test_plaintext_credential_consent_gate() -> None:
    vm = PublishWorkflowViewModel(consent_given=False)
    assert not vm.can_save_plaintext_credentials()
    assert not vm.save_plaintext_credentials({"token": "x"})

    vm.consent_given = True
    assert vm.can_save_plaintext_credentials()
    assert vm.save_plaintext_credentials({"token": "x"})
    assert vm.load_plaintext_credentials()["token"] == "x"
