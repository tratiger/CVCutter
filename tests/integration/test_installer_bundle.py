"""Installer packaging validation scaffolds for US7 (T079)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_MAX_INSTALLER_BYTES = 2 * 1024 * 1024 * 1024


def _installer_bundle_root() -> Path | None:
    """Locate the expanded installer bundle directory when present."""
    candidate = Path("dist") / "CVCutter"
    if candidate.exists() and candidate.is_dir():
        return candidate
    return None


def _skip_when_bundle_missing() -> None:
    """Skip when installer output is unavailable or built in one-file mode."""
    if (Path("dist") / "CVCutter.exe").exists():
        pytest.skip("One-file installer build detected; expanded bundle assertions are not applicable.")
    pytest.skip("Installer bundle not found. Build installer artifacts before running this test.")


def test_installer_bundle_contains_required_models_and_assets_scaffold() -> None:
    """Validate that packaged runtime assets/models are bundled in installer output."""
    bundle_root = _installer_bundle_root()
    if bundle_root is None:
        _skip_when_bundle_missing()

    required_assets = (
        bundle_root / "src" / "favicon.ico",
        bundle_root / "flet",
    )
    required_model_candidates = {
        "yolov8n": (bundle_root / "models" / "yolov8n.pt",),
        "whisper": (
            bundle_root / "models" / "whisper",
            bundle_root / "models" / "whisper-base.bin",
        ),
        "audio-classifier": (
            bundle_root / "models" / "audio_classifier.onnx",
            bundle_root / "models" / "audio-classifier.onnx",
        ),
    }

    missing_assets = [path for path in required_assets if not path.exists()]
    missing_models = [
        model_name
        for model_name, candidates in required_model_candidates.items()
        if not any(candidate.exists() for candidate in candidates)
    ]
    assert missing_assets == []
    assert missing_models == []


def test_installer_bundle_total_size_under_2gb_scaffold() -> None:
    """Validate installer bundle footprint is below the 2GB ceiling."""
    bundle_root = _installer_bundle_root()
    if bundle_root is None:
        _skip_when_bundle_missing()

    total_bytes = sum(path.stat().st_size for path in bundle_root.rglob("*") if path.is_file())
    assert total_bytes < _MAX_INSTALLER_BYTES
