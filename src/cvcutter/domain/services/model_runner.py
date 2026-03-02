"""Protocols for ML inference adapters used by detection and mapping workflows.

These ports isolate model execution concerns so domain/application logic remains
independent from specific inference frameworks and model artifacts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from cvcutter.domain.services.types import (
        AudioChunk,
        ClassificationResult,
        Detection,
        TranscriptionResult,
        VideoFrame,
    )


@runtime_checkable
class VisualDetectorRunner(Protocol):
    """Port for visual object detection model inference."""

    def detect(self, frame: VideoFrame) -> list[Detection]:
        """Run object detection on a single video frame and return labeled detections."""
        ...

    def model_version(self) -> str:
        """Return model identifier/version for reproducible checkpoint tracking."""
        ...


@runtime_checkable
class SpeechTranscriber(Protocol):
    """Port for speech-to-text transcription."""

    def transcribe(self, audio_path: Path, language: str = "ja") -> TranscriptionResult:
        """Transcribe audio into text and timestamped segments."""
        ...

    def model_version(self) -> str:
        """Return model identifier/version for reproducible checkpoint tracking."""
        ...


@runtime_checkable
class AudioContentClassifier(Protocol):
    """Port for short-window audio content classification."""

    def classify(self, audio_chunk: AudioChunk) -> list[ClassificationResult]:
        """Classify a short chunk (e.g., one second) into scored content labels."""
        ...

    def model_version(self) -> str:
        """Return model identifier/version for reproducible checkpoint tracking."""
        ...

