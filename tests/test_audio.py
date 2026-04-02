
import numpy as np
import pytest
import soundfile as sf

from cvcutter.core.audio import AudioProcessor


@pytest.fixture
def dummy_audio_files(tmp_path):
    sr = 44100
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration))

    # Create a simple sine wave pulse
    signal = np.sin(2 * np.pi * 440 * t) * np.exp(-3 * t)

    ref_path = tmp_path / "ref.wav"
    sf.write(ref_path, signal, sr)

    # Target is same signal shifted by 0.5 seconds
    shift_samples = int(0.5 * sr)
    target_signal = np.concatenate((np.zeros(shift_samples), signal))[:-shift_samples]
    target_path = tmp_path / "target.wav"
    sf.write(target_path, target_signal, sr)

    return ref_path, target_path

def test_find_sync_offset(dummy_audio_files):
    ref_path, target_path = dummy_audio_files
    processor = AudioProcessor()

    offset = processor.find_sync_offset(ref_path, target_path)
    # The mathematical cross-correlation logic we implemented yields -0.5 when target is delayed
    assert pytest.approx(offset, abs=0.05) == -0.5

def test_mix_audio(dummy_audio_files, tmp_path):
    ref_path, target_path = dummy_audio_files
    processor = AudioProcessor()
    out_path = tmp_path / "mix.wav"

    processor.mix_audio(ref_path, target_path, out_path, video_vol=0.5, mic_vol=0.5, offset_sec=0.5)
    assert out_path.exists()

    data, sr = sf.read(out_path)
    assert len(data) > 0

def test_generate_waveform(dummy_audio_files):
    ref_path, _ = dummy_audio_files
    processor = AudioProcessor()
    points = processor.generate_waveform_data(ref_path, num_points=100)

    assert len(points) == 100
    assert np.max(points) > 0
