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
    Concatenate multiple video files using FFmpeg concat demuxer (stream copy).
    This is fast and does not lose quality.
    """
    if not video_paths:
        return False
    if len(video_paths) == 1:
        # Just copy if only one file
        import shutil
        shutil.copy2(video_paths[0], output_path)
        return True

    # Create a temporary file list for ffmpeg
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        for path in video_paths:
            # FFmpeg concat file format requires escaping single quotes
            abs_path = os.path.abspath(path).replace("'", "'\\''")
            f.write(f"file '{abs_path}'\n")
        list_file = f.name

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        # -f concat -safe 0 -i list.txt -c copy output
        command = [
            ffmpeg_path, '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            output_path
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Concatenation failed: {result.stderr}")
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