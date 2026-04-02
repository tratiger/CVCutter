import os

import numpy as np
import pytest
import soundfile as sf
from moviepy import ColorClip

from cvcutter.core.analysis import MultimodalAnalyzer


@pytest.fixture
def dummy_audio(tmp_path):
    aud_path = tmp_path / "test_clap.wav"
    sr = 22050
    t = np.linspace(0, 5.0, int(sr * 5.0))
    # Create silent + loud burst + silent
    signal = np.zeros_like(t)
    signal[int(sr*1.0):int(sr*4.0)] = np.random.normal(0, 0.8, int(sr*3.0)) # "Clapping" noise
    sf.write(aud_path, signal, sr)
    return aud_path

@pytest.fixture
def dummy_video(tmp_path):
    vid_path = tmp_path / "test_bow.mp4"
    clip = ColorClip(size=(320, 240), color=(0, 255, 0), duration=2.0)
    clip.write_videofile(str(vid_path), fps=10, codec="libx264", logger=None)
    return vid_path

def test_detect_clapping(dummy_audio):
    analyzer = MultimodalAnalyzer()
    segments = analyzer.detect_clapping(dummy_audio, threshold=0.1)

    assert len(segments) > 0
    # Should detect the loud burst between 1.0s and 4.0s
    start, end = segments[0]
    assert 0.5 < start < 1.5
    assert 3.5 < end < 4.5

def test_detect_bowing(dummy_video):
    analyzer = MultimodalAnalyzer()
    # A blank green video won't have humans, so should return empty list
    timestamps = analyzer.detect_bowing(dummy_video)
    assert isinstance(timestamps, list)
    assert len(timestamps) == 0

@pytest.mark.skipif("GITHUB_ACTIONS" in os.environ, reason="Whisper download too slow for CI")
def test_transcribe_mc(dummy_audio):
    analyzer = MultimodalAnalyzer(whisper_model_size="tiny")
    # Will just transcribe random noise, so might be empty or nonsense, but shouldn't crash
    text = analyzer.transcribe_mc(dummy_audio, start_time=0.0, duration=1.0)
    assert isinstance(text, str)
