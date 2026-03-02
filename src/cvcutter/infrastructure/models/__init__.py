"""Infrastructure model runners."""

from cvcutter.infrastructure.models.audio_classifier_runner import OnnxAudioClassifierRunner
from cvcutter.infrastructure.models.yolo_runner import YoloModelRunner

__all__ = ["OnnxAudioClassifierRunner", "YoloModelRunner"]
