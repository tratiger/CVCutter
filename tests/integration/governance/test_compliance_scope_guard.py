from cvcutter.application.services.compliance_scope_service import verify_scope


def test_compliance_scope_guard() -> None:
    assert verify_scope({"desktop_only"})
    assert not verify_scope({"mobile_ui"})
