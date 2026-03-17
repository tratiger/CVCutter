from cvcutter.app import AppBootstrap
from cvcutter.infrastructure.packaging.platform_compatibility import PlatformCompatibilityChecker


def test_packaged_runtime_smoke() -> None:
    assert "status" in AppBootstrap(PlatformCompatibilityChecker()).launch()
