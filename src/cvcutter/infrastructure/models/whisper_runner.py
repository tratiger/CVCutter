"""Whisper speech transcription adapter with graceful local fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cvcutter.domain.services.model_runner import SpeechTranscriber
from cvcutter.domain.services.types import TranscriptionResult, TranscriptionSegment


class WhisperRunner(SpeechTranscriber):
    """Run local Whisper transcription while tolerating missing runtime dependencies."""

    def __init__(self, *, model_name: str = "small") -> None:
        self._model_name = model_name
        self._model: Any | None = None

    def transcribe(self, audio_path: Path, language: str = "ja") -> TranscriptionResult:
        target_path = Path(audio_path)
        model = self._ensure_model()
        if model is None or not target_path.exists():
            return self._empty_result(language)

        try:
            raw_result = model.transcribe(str(target_path), language=language)
        except Exception:
            return self._empty_result(language)

        text = str(raw_result.get("text", "")).strip() if isinstance(raw_result, dict) else ""
        raw_segments = raw_result.get("segments", []) if isinstance(raw_result, dict) else []
        segments: list[TranscriptionSegment] = []
        if isinstance(raw_segments, list):
            for raw_segment in raw_segments:
                if not isinstance(raw_segment, dict):
                    continue
                start = float(raw_segment.get("start", 0.0))
                end = float(raw_segment.get("end", start))
                if end <= start:
                    continue
                confidence = _clamp(
                    float(
                        raw_segment.get(
                            "confidence",
                            1.0 - float(raw_segment.get("no_speech_prob", 0.5)),
                        ),
                    ),
                )
                segments.append(
                    TranscriptionSegment(
                        text=str(raw_segment.get("text", "")).strip(),
                        start_seconds=start,
                        end_seconds=end,
                        confidence=confidence,
                    ),
                )

        overall_confidence = _clamp(
            sum(segment.confidence for segment in segments) / len(segments)
            if segments
            else (0.8 if text else 0.0),
        )
        return TranscriptionResult(
            text=text,
            segments=segments,
            language=language,
            confidence=overall_confidence,
        )

    def model_version(self) -> str:
        return f"whisper:{self._model_name}"

    def _ensure_model(self) -> Any | None:
        if self._model is not None:
            return self._model
        try:
            import whisper  # type: ignore[import-not-found]
        except Exception:
            return None
        try:
            self._model = whisper.load_model(self._model_name)
        except Exception:
            self._model = None
        return self._model

    @staticmethod
    def _empty_result(language: str) -> TranscriptionResult:
        return TranscriptionResult(text="", segments=[], language=language, confidence=0.0)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
