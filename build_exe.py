import subprocess
import sys
from pathlib import Path


def main():
    print("Building CVCutter Executable using PyInstaller...")
    
    # We use flet pack for packaging flet apps, which wraps pyinstaller
    # But using pyinstaller directly gives us more control over mediapipe/whisper data files if needed.
    # Let's use `flet pack` as it's the recommended way for Flet apps.

    src_dir = Path("src")
    main_file = src_dir / "cvcutter" / "main.py"

    if not main_file.exists():
        print(f"Error: Could not find main entry point at {main_file}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "flet", "pack", str(main_file),
        "--name", "CVCutter",
        "--product-name", "CVCutter",
        "--product-version", "0.2.0",
        "--copyright", "MIT License"
    ]

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\nBuild successful! Check the 'dist' directory.")
    else:
        print("\nBuild failed.")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
