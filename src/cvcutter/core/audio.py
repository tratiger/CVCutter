from pathlib import Path

import av
import librosa
import numpy as np
import soundfile as sf
from scipy import signal

from cvcutter.utils.exceptions import AudioProcessingError
from cvcutter.utils.logger import logger


class AudioProcessor:
    def __init__(self, sr: int = 44100):
        self.sr = sr

    def extract_audio_from_video(self, video_path: Path, output_path: Path) -> Path:
        """Extracts audio from video efficiently using PyAV."""
        logger.info(f"Extracting audio from {video_path} to {output_path}")
        try:
            container = av.open(str(video_path))
            audio_stream = next((s for s in container.streams if s.type == 'audio'), None)

            if not audio_stream:
                raise AudioProcessingError("No audio stream found in video.")

            output_container = av.open(str(output_path), 'w')
            out_stream = output_container.add_stream('pcm_s16le', rate=self.sr)

            for frame in container.decode(audio_stream):
                frame.pts = None
                for packet in out_stream.encode(frame):
                    output_container.mux(packet)

            for packet in out_stream.encode(None):
                output_container.mux(packet)

            container.close()
            output_container.close()
            return output_path
        except Exception as e:
            logger.error(f"Failed to extract audio: {e}")
            raise AudioProcessingError(f"Failed to extract audio: {e}")

    def find_sync_offset(self, ref_audio_path: Path, target_audio_path: Path, max_duration: int = 300) -> float:
        """
        Finds the time offset (in seconds) to sync target_audio to ref_audio using cross-correlation.
        Positive offset means target_audio starts AFTER ref_audio.
        Analyzes up to max_duration seconds to save memory.
        """
        logger.info(f"Calculating sync offset between {ref_audio_path} and {target_audio_path}")
        try:
            # Load only a chunk to save memory
            y_ref, _ = librosa.load(ref_audio_path, sr=self.sr, mono=True, duration=max_duration)
            y_tgt, _ = librosa.load(target_audio_path, sr=self.sr, mono=True, duration=max_duration)

            # Use FFT-based cross correlation for speed
            correlation = signal.correlate(y_ref, y_tgt, mode='full', method='fft')

            # Find the peak
            delay_samples = np.argmax(correlation) - (len(y_tgt) - 1)
            offset_seconds = delay_samples / self.sr

            logger.debug(f"Sync offset calculated: {offset_seconds:.3f}s")
            return float(offset_seconds)
        except Exception as e:
            raise AudioProcessingError(f"Failed to find sync offset: {e}")

    def mix_audio(self, video_audio_path: Path, mic_audio_path: Path, output_path: Path,
                  video_vol: float = 0.2, mic_vol: float = 0.8, offset_sec: float = 0.0) -> Path:
        """
        Mixes two audio files with given volume ratios and an offset.
        Applies a basic high-pass filter to the mic to reduce rumble.
        """
        logger.info(f"Mixing audio. Video vol: {video_vol}, Mic vol: {mic_vol}, Offset: {offset_sec}s")
        try:
            # For a production app handling huge files, this should ideally be chunked or use ffmpeg directly.
            # But librosa.load reads into memory. We will use soundfile blocks for memory efficiency if files are large.
            # However, for simplicity and typical concert lengths, we can use soundfile to read/write blocks.

            # Simple approach: ffmpeg command via subprocess might be safest for huge files,
            # but let's implement a block-based Python mixer.

            # This is a simplified in-memory mix for the example. A true stream mixer requires careful buffer management.
            y_vid, _ = librosa.load(video_audio_path, sr=self.sr, mono=False)
            y_mic, _ = librosa.load(mic_audio_path, sr=self.sr, mono=False)

            # Ensure 2D arrays (channels, samples)
            if y_vid.ndim == 1: y_vid = np.expand_dims(y_vid, 0)
            if y_mic.ndim == 1: y_mic = np.expand_dims(y_mic, 0)

            # Pad the one that starts later
            offset_samples = int(abs(offset_sec) * self.sr)
            channels = max(y_vid.shape[0], y_mic.shape[0])

            if offset_sec > 0:
                # mic starts after video
                pad = np.zeros((channels, offset_samples))
                y_mic = np.concatenate((pad, y_mic), axis=1)
            elif offset_sec < 0:
                # video starts after mic
                pad = np.zeros((channels, offset_samples))
                y_vid = np.concatenate((pad, y_vid), axis=1)

            # Match lengths
            max_len = max(y_vid.shape[1], y_mic.shape[1])
            y_vid_padded = np.zeros((channels, max_len))
            y_mic_padded = np.zeros((channels, max_len))

            y_vid_padded[:, :y_vid.shape[1]] = y_vid
            y_mic_padded[:, :y_mic.shape[1]] = y_mic

            # Apply basic high pass to mic
            sos = signal.butter(10, 80, 'hp', fs=self.sr, output='sos')
            y_mic_filtered = signal.sosfilt(sos, y_mic_padded)

            mix = (y_vid_padded * video_vol) + (y_mic_filtered * mic_vol)

            # Normalize to avoid clipping
            max_val = np.max(np.abs(mix))
            if max_val > 1.0:
                mix = mix / max_val

            sf.write(output_path, mix.T, self.sr)
            return output_path

        except Exception as e:
            raise AudioProcessingError(f"Audio mixing failed: {e}")

    def generate_waveform_data(self, audio_path: Path, num_points: int = 1000) -> np.ndarray:
        """Generates downsampled waveform array for UI rendering."""
        try:
            y, _ = librosa.load(audio_path, sr=self.sr, mono=True)
            # Downsample by taking max absolute value in blocks
            block_size = max(1, len(y) // num_points)
            downsampled = [np.max(np.abs(y[i:i+block_size])) for i in range(0, len(y), block_size)]
            return np.array(downsampled[:num_points])
        except Exception as e:
            raise AudioProcessingError(f"Failed to generate waveform: {e}")
