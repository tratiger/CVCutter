from __future__ import annotations

from cvcutter.application.services.integration_compatibility_service import check_compatibility


def test_compatibility_check_passes_when_version_matches_pin() -> None:
    result = check_compatibility("youtube", "v3", {"youtube": "v3"})
    assert result["compatible"]
    assert result["reason"] == "ok"


def test_compatibility_check_blocks_when_version_mismatches_pin() -> None:
    result = check_compatibility("youtube", "v4", {"youtube": "v3"})
    assert not result["compatible"]
    assert result["reason"] == "pinned_version_mismatch"
    assert result["guidance"] == "update_provider_or_pin"
