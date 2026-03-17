from cvcutter.presentation.flet_app.viewmodels.setup_wizard_viewmodel import SetupWizardViewModel


def test_setup_wizard_validation() -> None:
    vm = SetupWizardViewModel(source_path="in", output_path="out")
    assert vm.validate()
