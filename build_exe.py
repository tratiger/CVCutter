"""Build CVCutter executable with Flet runtime assets and local model bundling."""

from __future__ import annotations

import shutil
from pathlib import Path

import PyInstaller.__main__

PROJECT_ROOT = Path(__file__).resolve().parent
ENTRYPOINT = PROJECT_ROOT / "src" / "cvcutter" / "main.py"
ICON_PATH = PROJECT_ROOT / "src" / "favicon.ico"
_BUILD_DIR_NAMES = ("build", "dist")


def _windows_add_data_arg(source: Path, target: str) -> str:
    return f"--add-data={source};{target}"


def _collect_model_add_data_args() -> list[str]:
    model_locations: list[tuple[Path, str]] = [
        (PROJECT_ROOT / "yolov8n.pt", "models"),
        (PROJECT_ROOT / "models" / "yolov8n.pt", "models"),
        (PROJECT_ROOT / "audio_classifier.onnx", "models"),
        (PROJECT_ROOT / "models" / "audio_classifier.onnx", "models"),
        (PROJECT_ROOT / "models" / "audio-classifier.onnx", "models"),
        (PROJECT_ROOT / "models" / "whisper", "models/whisper"),
        (PROJECT_ROOT / "assets" / "whisper", "models/whisper"),
    ]
    arguments: list[str] = []
    for source, target in model_locations:
        if source.exists():
            arguments.append(_windows_add_data_arg(source, target))
    return arguments


def _clean_previous_builds() -> None:
    for directory_name in _BUILD_DIR_NAMES:
        target = PROJECT_ROOT / directory_name
        if target.exists():
            shutil.rmtree(target)


def build() -> None:
    """Build one-file desktop executable using the layered Flet entry point."""
    _clean_previous_builds()
    command: list[str] = [
        str(ENTRYPOINT),
        "--name=CVCutter",
        "--windowed",
        "--onefile",
        "--noconfirm",
        "--clean",
        "--collect-submodules=cvcutter",
        "--collect-submodules=flet",
        "--collect-submodules=flet_desktop",
        "--collect-submodules=cv2",
        "--collect-submodules=librosa",
        "--collect-submodules=scipy",
        "--collect-submodules=imageio_ffmpeg",
        "--collect-submodules=ultralytics",
        "--collect-submodules=whisper",
        "--collect-submodules=onnxruntime",
        "--collect-submodules=googleapiclient",
        "--collect-data=flet",
        "--collect-data=flet_desktop",
        "--collect-data=imageio_ffmpeg",
        "--copy-metadata=flet",
        "--copy-metadata=flet-desktop",
        "--copy-metadata=openai-whisper",
        "--copy-metadata=ultralytics",
        "--exclude-module=customtkinter",
        "--exclude-module=moviepy",
        "--exclude-module=matplotlib",
        "--exclude-module=IPython",
        "--exclude-module=jedi",
        "--exclude-module=notebook",
    ]
    if ICON_PATH.exists():
        command.append(f"--icon={ICON_PATH}")
    command.extend(_collect_model_add_data_args())
    PyInstaller.__main__.run(command)


if __name__ == "__main__":
    build()
