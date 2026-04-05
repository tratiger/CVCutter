from pathlib import Path
from typing import List, Tuple

import av
import librosa
from faster_whisper import WhisperModel

from cvcutter.utils.exceptions import MultimodalAnalysisError
from cvcutter.utils.logger import logger


class MultimodalAnalyzer:
    def __init__(self, whisper_model_size: str = "tiny"):
        self.whisper_model_size = whisper_model_size
        self._whisper_model = None
        self._mp_pose = None
        self._pose = None

    @property
    def whisper_model(self):
        if self._whisper_model is None:
            logger.info(f"Loading faster-whisper model: {self.whisper_model_size}")
            self._whisper_model = WhisperModel(self.whisper_model_size, device="cpu", compute_type="int8")
        return self._whisper_model

    def _init_mediapipe(self):
        if self._mp_pose is None:
            try:
                import mediapipe as mp
                from mediapipe.tasks import python
                from mediapipe.tasks.python import vision
                import os
                import urllib.request

                model_path = "pose_landmarker.task"
                if not os.path.exists(model_path):
                    logger.info("Downloading mediapipe pose model...")
                    url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
                    urllib.request.urlretrieve(url, model_path)

                base_options = python.BaseOptions(model_asset_path=model_path)
                options = vision.PoseLandmarkerOptions(
                    base_options=base_options,
                    output_segmentation_masks=False)

                self._pose = vision.PoseLandmarker.create_from_options(options)
                self._mp_pose = "loaded"
            except Exception as e:
                logger.error(f"Failed to load mediapipe pose: {e}. Bowing detection will return empty.")
                self._mp_pose = "failed" # Mark as failed to avoid re-trying

    def transcribe_mc(self, audio_path: Path, start_time: float, duration: float = 60.0) -> str:
        """Transcribes MC speech in a specific audio segment."""
        logger.info(f"Transcribing MC segment starting at {start_time}s for {duration}s")
        try:
            y, sr = librosa.load(audio_path, sr=16000, offset=start_time, duration=duration, mono=True)
            segments, info = self.whisper_model.transcribe(y, beam_size=5, language="ja")
            transcript = " ".join([segment.text for segment in segments])
            logger.debug(f"Transcription result: {transcript}")
            return transcript.strip()
        except Exception as e:
            raise MultimodalAnalysisError(f"Transcription failed: {e}")

    def detect_clapping(self, audio_path: Path, threshold: float = 0.035) -> List[Tuple[float, float]]:
        """Detects clapping/applause using smoothed audio energy heuristics."""
        logger.info(f"Analyzing audio for clapping/applause: {audio_path}")
        try:
            import numpy as np
            sr = 22050
            hop_length = 512

            # We process the entire file to allow numpy convolutions.
            # For memory constraint, we load it mono and low SR.
            y, sr = librosa.load(str(audio_path), sr=sr, mono=True)
            audio_duration = librosa.get_duration(y=y, sr=sr)

            clapping_segments = []
            energy = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]

            # Smooth energy to prevent tiny drops from breaking a segment
            energy_smoothed = np.convolve(energy, np.ones(10)/10, mode='same')
            high_energy_mask = energy_smoothed > threshold

            in_clap = False
            clap_start = 0.0

            for i, is_high in enumerate(high_energy_mask):
                t = (i * hop_length) / sr
                if is_high and not in_clap:
                    in_clap = True
                    clap_start = t
                elif not is_high and in_clap:
                    in_clap = False
                    if t - clap_start > 1.0:
                        clapping_segments.append((clap_start, min(t, audio_duration)))

            if in_clap:
                t = len(high_energy_mask) * hop_length / sr
                if t - clap_start > 1.0:
                    clapping_segments.append((clap_start, min(t, audio_duration)))

            return clapping_segments
        except Exception as e:
            raise MultimodalAnalysisError(f"Clapping detection failed: {e}")

    def detect_silence(self, audio_path: Path, threshold: float = 0.005, min_silence_duration: float = 3.0) -> List[Tuple[float, float]]:
        """Detects periods of silence or very low noise indicating gaps between performances."""
        logger.info(f"Analyzing audio for silence gaps: {audio_path}")
        try:
            import numpy as np
            sr = 22050
            hop_length = 512
            y, sr = librosa.load(str(audio_path), sr=sr, mono=True)
            energy = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]

            energy_smoothed = np.convolve(energy, np.ones(5)/5, mode='same')
            low_energy_mask = energy_smoothed < threshold

            silences = []
            in_silence = False
            silence_start = 0.0

            for i, is_low in enumerate(low_energy_mask):
                t = (i * hop_length) / sr
                if is_low and not in_silence:
                    in_silence = True
                    silence_start = t
                elif not is_low and in_silence:
                    in_silence = False
                    if t - silence_start > min_silence_duration:
                        silences.append((silence_start, t))

            if in_silence:
                t = len(low_energy_mask) * hop_length / sr
                if t - silence_start > min_silence_duration:
                    silences.append((silence_start, t))

            return silences
        except Exception as e:
            logger.error(f"Silence detection failed: {e}")
            return []

    def detect_bowing(self, video_path: Path, sample_rate: float = 1.0) -> List[float]:
        """Analyzes video frames using MediaPipe to detect bowing."""
        logger.info(f"Analyzing video for bowing: {video_path}")
        self._init_mediapipe()

        if self._mp_pose == "failed":
            return [] # Graceful degradation

        import mediapipe as mp
        bowing_timestamps = []
        try:
            container = av.open(str(video_path))
            video_stream = next((s for s in container.streams if s.type == 'video'), None)
            if not video_stream:
                raise ValueError("No video stream found")

            fps = video_stream.average_rate
            if fps is None or fps == 0:
                fps = 30

            frame_interval = int(fps / sample_rate)

            for i, frame in enumerate(container.decode(video_stream)):
                if i % frame_interval != 0:
                    continue

                timestamp = frame.time
                if timestamp is None:
                    timestamp = i / fps

                image = frame.to_ndarray(format='rgb24')
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)

                results = self._pose.detect(mp_image)

                if results.pose_landmarks and len(results.pose_landmarks) > 0:
                    landmarks = results.pose_landmarks[0]
                    # 11 is LEFT_SHOULDER, 23 is LEFT_HIP according to Mediapipe docs
                    l_shoulder = landmarks[11]
                    l_hip = landmarks[23]

                    y_diff = l_hip.y - l_shoulder.y
                    if y_diff < 0.15:
                        bowing_timestamps.append(float(timestamp))

            container.close()
            return bowing_timestamps
        except Exception as e:
            raise MultimodalAnalysisError(f"Bowing detection failed: {e}")
