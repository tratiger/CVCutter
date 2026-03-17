from cvcutter.application.services.runtime_preflight_service import runtime_profile


def test_cpu_fallback_without_acceleration() -> None:
    assert runtime_profile(False) == "cpu_fallback"
