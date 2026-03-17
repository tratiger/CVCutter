from cvcutter.application.services.cleanup_service import cleanup_artifact


def test_cleanup_retention_protects_audit() -> None:
    assert cleanup_artifact("audit:event")[0] is False
