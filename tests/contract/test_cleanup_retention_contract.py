from cvcutter.application.services.cleanup_service import cleanup_artifact


def test_cleanup_retention_protects_audit() -> None:
    result = cleanup_artifact("audit:event")
    assert result.event_type == "cleanup.rejected"
    assert result.target_class == "protected_minimal_audit"
    assert result.reason == "policy_protected"
