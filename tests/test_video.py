
import numpy as np
import pytest
import soundfile as sf
from moviepy import ColorClip

from cvcutter.core.video import VideoProcessor


@pytest.fixture
def dummy_video_and_audio(tmp_path):
    vid_path = tmp_path / "dummy.mp4"
    aud_path = tmp_path / "dummy_audio.wav"

    # Create 2 sec silent video
    clip = ColorClip(size=(320, 240), color=(255, 0, 0), duration=2.0)
    clip.write_videofile(str(vid_path), fps=10, codec="libx264", logger=None)

    # Create 2 sec audio
    sr = 44100
    t = np.linspace(0, 2.0, int(sr * 2.0))
    signal = np.sin(2 * np.pi * 440 * t)
    sf.write(aud_path, signal, sr)

    return vid_path, aud_path

def test_apply_audio(dummy_video_and_audio, tmp_path):
    vid_path, aud_path = dummy_video_and_audio
    processor = VideoProcessor(use_gpu=False)

    out_path = tmp_path / "vid_with_audio.mp4"
    processor.apply_audio(vid_path, aud_path, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0

def test_render_clip(dummy_video_and_audio, tmp_path):
    vid_path, _ = dummy_video_and_audio
    processor = VideoProcessor(use_gpu=False)

    out_path = tmp_path / "clip.mp4"
    # Note: MoviePy TextClip requires ImageMagick. We might get an error if not installed.
    # To be safe for testing environment, we test without telop first.
    processor.render_clip(vid_path, out_path, start_time=0.5, end_time=1.5, telop_text=None)

    assert out_path.exists()
    assert out_path.stat().st_size > 0
