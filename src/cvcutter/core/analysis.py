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
                # mediapipe library might not be fully supported on standard python 3.13 without some hacks
                # For this environment we try to import correctly from mediapipe.tasks if possible
                # However, since the older `mediapipe` version uses mediapipe.python which fails,
                # we will gracefully degrade if MediaPipe fails to load, returning empty bowing detection
                import mediapipe as mp
                self._mp_pose = mp.solutions.pose
                self._pose = self._mp_pose.Pose(
                    static_image_mode=False,
                    model_complexity=0,
                    enable_segmentation=False,
                    min_detection_confidence=0.5
                )
            except (ImportError, AttributeError) as e:
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

    def detect_clapping(self, audio_path: Path, threshold: float = 0.5) -> List[Tuple[float, float]]:
        """Detects clapping using audio energy heuristics."""
        logger.info(f"Analyzing audio for clapping/applause: {audio_path}")
        try:
            sr = 22050
            hop_length = 512
            stream = librosa.stream(str(audio_path), block_length=256, frame_length=2048, hop_length=hop_length)

            clapping_segments = []
            current_time = 0.0
            in_clap = False
            clap_start = 0.0

            for y_block in stream:
                energy = librosa.feature.rms(y=y_block, frame_length=2048, hop_length=hop_length)[0]
                high_energy_mask = energy > threshold

                for i, is_high in enumerate(high_energy_mask):
                    t = current_time + (i * hop_length) / sr
                    if is_high and not in_clap:
                        in_clap = True
                        clap_start = t
                    elif not is_high and in_clap:
                        in_clap = False
                        if t - clap_start > 2.0:
                            clapping_segments.append((clap_start, t))

                current_time += len(y_block) / sr

            if in_clap:
                clapping_segments.append((clap_start, current_time))

            return clapping_segments
        except Exception as e:
            raise MultimodalAnalysisError(f"Clapping detection failed: {e}")

    def detect_bowing(self, video_path: Path, sample_rate: float = 1.0) -> List[float]:
        """Analyzes video frames using MediaPipe to detect bowing."""
        logger.info(f"Analyzing video for bowing: {video_path}")
        self._init_mediapipe()

        if self._mp_pose == "failed":
            return [] # Graceful degradation

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
                results = self._pose.process(image)

                if results.pose_landmarks:
                    landmarks = results.pose_landmarks.landmark
                    # Using PoseLandmark indices directly to avoid extra imports here
                    # 11 is LEFT_SHOULDER, 23 is LEFT_HIP according to Mediapipe docs
                    l_shoulder = landmarks[11]
                    l_hip = landmarks[23]

                    y_diff = l_hip.y - l_shoulder.y
                    if y_diff < 0.1:
                        bowing_timestamps.append(float(timestamp))

            container.close()
            return bowing_timestamps
        except Exception as e:
            raise MultimodalAnalysisError(f"Bowing detection failed: {e}")
