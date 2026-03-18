from __future__ import annotations

from cvcutter.infrastructure.packaging.platform_compatibility import PlatformCompatibilityChecker


def test_windows_10_amd64_is_supported() -> None:
    result = PlatformCompatibilityChecker().ensure_supported(
        system="Windows",
        release="10",
        machine="AMD64",
    )
    assert result["supported"]
    assert result["reason"] == "ok"


def test_windows_8_is_blocked() -> None:
    result = PlatformCompatibilityChecker().ensure_supported(
        system="Windows",
        release="8.1",
        machine="AMD64",
    )
    assert not result["supported"]
    assert result["reason"] == "unsupported_windows_version"


def test_windows_32bit_is_blocked() -> None:
    result = PlatformCompatibilityChecker().ensure_supported(
        system="Windows",
        release="11",
        machine="x86",
    )
    assert not result["supported"]
    assert result["reason"] == "unsupported_architecture"


def test_macos_13_arm64_is_supported() -> None:
    result = PlatformCompatibilityChecker().ensure_supported(
        system="Darwin",
        release="13.5",
        machine="arm64",
    )
    assert result["supported"]
    assert result["reason"] == "ok"


def test_macos_12_is_blocked() -> None:
    result = PlatformCompatibilityChecker().ensure_supported(
        system="Darwin",
        release="12.7",
        machine="x86_64",
    )
    assert not result["supported"]
    assert result["reason"] == "unsupported_macos_version"


def test_darwin_kernel_version_21_maps_to_unsupported_macos_12() -> None:
    result = PlatformCompatibilityChecker().ensure_supported(
        system="Darwin",
        release="21.6.0",
        machine="x86_64",
    )
    assert not result["supported"]
    assert result["reason"] == "unsupported_macos_version"


def test_darwin_kernel_version_22_maps_to_supported_macos_13() -> None:
    result = PlatformCompatibilityChecker().ensure_supported(
        system="Darwin",
        release="22.1.0",
        machine="arm64",
    )
    assert result["supported"]
    assert result["reason"] == "ok"


def test_non_target_os_is_blocked() -> None:
    result = PlatformCompatibilityChecker().ensure_supported(
        system="Linux",
        release="6.8",
        machine="x86_64",
    )
    assert not result["supported"]
    assert result["reason"] == "unsupported_os"
