from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class BuildConfig:
    app_name: str = "CVCutter"
    target_platforms: tuple[str, ...] = ("windows", "macos")


def get_build_config() -> BuildConfig:
    return BuildConfig()


def _build_with_pyinstaller(output_dir: Path, app_name: str) -> Path | None:
    try:
        from PyInstaller import __main__ as pyinstaller_main
    except ModuleNotFoundError:
        return None
    entry_script = Path(__file__).resolve().parent / "run_app.py"
    pyinstaller_main.run(
        [
            "--noconfirm",
            "--onefile",
            "--noupx",
            f"--name={app_name}",
            f"--distpath={output_dir}",
            str(entry_script),
        ]
    )
    artifact_name = f"{app_name}.exe" if os.name == "nt" else app_name
    artifact = output_dir / artifact_name
    return artifact if artifact.exists() else None


def build(dist_dir: Path | None = None) -> Path:
    config = get_build_config()
    output_dir = dist_dir or Path("dist")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = _build_with_pyinstaller(output_dir, config.app_name)
    if artifact is None:
        raise RuntimeError("PyInstaller is required to build a distributable artifact.")
    manifest = output_dir / f"{config.app_name.lower()}-build.json"
    manifest.write_text(
        json.dumps(
            {
                "app_name": config.app_name,
                "target_platforms": list(config.target_platforms),
                "artifact": artifact.name,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return artifact


def main() -> int:
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
