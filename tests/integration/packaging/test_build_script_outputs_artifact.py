from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def test_build_script_creates_manifest_artifact(tmp_path: Path) -> None:
    module_name = "build_exe_module_for_test"
    module_path = Path(__file__).resolve().parents[3] / "build_exe.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        try:
            artifact = module.build(dist_dir=tmp_path)
        except RuntimeError as error:
            assert "PyInstaller" in str(error)
            return
    finally:
        sys.modules.pop(module_name, None)
    assert artifact.exists()
    assert artifact.suffix in {".exe", ""}
    manifest = tmp_path / "cvcutter-build.json"
    assert manifest.exists()
