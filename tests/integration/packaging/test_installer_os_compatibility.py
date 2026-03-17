from cvcutter.infrastructure.packaging.platform_compatibility import PlatformCompatibilityChecker


def test_platform_checker_shape() -> None:
    result = PlatformCompatibilityChecker().ensure_supported()
    assert "supported" in result
