"""Detection domain package."""

from cvcutter.domain.detection.audio_classifier import AudioContentClassifier
from cvcutter.domain.detection.audio_energy import AudioEnergyDetector
from cvcutter.domain.detection.detector import CompositeDetector, DetectionFusionConfig
from cvcutter.domain.detection.visual_detector import VisualActivityDetector

__all__ = [
    "AudioContentClassifier",
    "AudioEnergyDetector",
    "CompositeDetector",
    "DetectionFusionConfig",
    "VisualActivityDetector",
]
