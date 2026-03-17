from cvcutter.presentation.flet_app.viewmodels.publish_workflow_viewmodel import PublishWorkflowViewModel


def test_plaintext_credential_consent_gate() -> None:
    assert not PublishWorkflowViewModel(consent_given=False).can_save_plaintext_credentials()
    assert PublishWorkflowViewModel(consent_given=True).can_save_plaintext_credentials()
