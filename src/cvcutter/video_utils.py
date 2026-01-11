import subprocess
import os
import sys
import tempfile
import shutil
import imageio_ffmpeg
from pathlib import Path
from typing import List

def get_app_data_path(filename: str) -> Path:
    """
    EXE実行時と開発環境の両方で、永続化すべきデータファイルの正しいパスを返す
    """
    if getattr(sys, 'frozen', False):
        # EXE本体があるディレクトリ
        base_path = Path(sys.executable).parent
    else:
        # プロジェクトルート
        base_path = Path(__file__).parent.parent.parent
    
    return base_path / filename

def concatenate_videos(video_paths: List[str], output_path: str) -> bool:
    """
    Concatenate multiple video files using FFmpeg's concat filter.
    This method re-encodes the video and audio streams, resetting timestamps
    to ensure a continuous timeline, which is crucial for subsequent processing.
    """
    if not video_paths:
        return False
    if len(video_paths) == 1:
        # If only one file, just copy it to avoid re-encoding.
        shutil.copy2(video_paths[0], output_path)
        return True

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Build the input part of the command: -i file1 -i file2 ...
    inputs = [arg for path in video_paths for arg in ['-i', path]]
    
    # Build the filter_complex part: [0:v][0:a][1:v][1:a]...concat=n=N:v=1:a=1[v][a]
    filter_inputs = "".join([f"[{i}:v][{i}:a]" for i in range(len(video_paths))])
    filter_complex = f"{filter_inputs}concat=n={len(video_paths)}:v=1:a=1[v][a]"

    try:
        command = [
            ffmpeg_path, '-y',
            *inputs,
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-map', '[a]',
            '-c:v', 'libx264', '-preset', 'medium', # Re-encode with standard settings
            '-c:a', 'aac', '-b:a', '192k',
            output_path
        ]
        
        print("Running FFmpeg with concat filter...")
        print(" ".join(command)) # For debugging

        # Using STARTUPINFO to hide the console window on Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        result = subprocess.run(command, capture_output=True, text=True, startupinfo=startupinfo)
        
        if result.returncode != 0:
            print(f"Concatenation with filter failed. Error:\n{result.stderr}")
            # Fallback to demuxer method if filter fails, as it's more robust for identical codecs
            print("Falling back to concat demuxer (stream copy)...")
            return _concatenate_with_demuxer(video_paths, output_path)
            
        print("Concatenation successful.")
        return True
    except Exception as e:
        print(f"An exception occurred during concatenation: {e}")
        return False

def _concatenate_with_demuxer(video_paths: List[str], output_path: str) -> bool:
    """Fallback to the faster but potentially problematic concat demuxer."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        for path in video_paths:
            abs_path = os.path.abspath(path).replace("'", "'\\''")
            f.write(f"file '{abs_path}'\n")
        list_file = f.name
    
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        command = [
            ffmpeg_path, '-y', '-f', 'concat', '-safe', '0', '-i', list_file,
            '-c', 'copy', output_path
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Fallback concatenation failed: {result.stderr}")
            return False
        return True
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)

def get_gpu_args() -> List[str]:
    """Detect if NVIDIA GPU is available and return appropriate ffmpeg args."""
    try:
        subprocess.run(['nvidia-smi'], capture_output=True, check=True)
        return ['-c:v', 'h264_nvenc', '-preset', 'p4', '-tune', 'hq']
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ['-c:v', 'libx264', '-preset', 'medium']