from cvcutter.application.services.export_readiness_service import export_ready


def test_low_confidence_requires_resolution() -> None:
    assert not export_ready(unresolved_reviews=1, unresolved_sync_flags=0)
