"""ONNX runtime adapter implementing the audio classifier protocol."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from cvcutter.domain.services.types import AudioChunk, ClassificationResult

_DEFAULT_LABELS = ("music", "speech", "applause", "silence")


class OnnxAudioClassifierRunner:
    """Run ONNX audio-content classifier inference on short audio windows."""

    def __init__(
        self,
        *,
        model_path: Path | str,
        labels: tuple[str, ...] = _DEFAULT_LABELS,
    ) -> None:
        self._model_path = Path(model_path)
        if not self._model_path.exists():
            raise FileNotFoundError(f"Audio classifier model file not found: {self._model_path}")
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("onnxruntime is required for audio classification.") from exc

        self._session = ort.InferenceSession(str(self._model_path))
        self._input_name = self._session.get_inputs()[0].name
        self._labels = tuple(str(label).strip().lower() for label in labels)

    def classify(self, audio_chunk: AudioChunk) -> list[ClassificationResult]:
        """Classify one audio chunk and return scored labels."""
        samples = np.asarray(audio_chunk.data, dtype=np.float32)
        if samples.size == 0:
            return []
        try:
            input_tensor = samples.reshape(1, -1)
            outputs = self._session.run(None, {self._input_name: input_tensor})
            if not outputs:
                return []

            logits = np.asarray(outputs[0], dtype=np.float32).reshape(-1)
            if logits.size == 0:
                return []
            probabilities = _softmax(logits)

            start_seconds = audio_chunk.start_seconds
            end_seconds = audio_chunk.start_seconds + audio_chunk.duration_seconds
            results: list[ClassificationResult] = []
            for index, confidence in enumerate(probabilities):
                label = self._labels[index] if index < len(self._labels) else f"class_{index}"
                results.append(
                    ClassificationResult(
                        label=label,
                        confidence=float(np.clip(confidence, 0.0, 1.0)),
                        start_seconds=start_seconds,
                        end_seconds=end_seconds,
                    ),
                )
            return results
        except Exception:
            return []

    def model_version(self) -> str:
        """Return deterministic model identifier for checkpointing."""
        return f"onnx:{self._model_path.name}"


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    exp = np.exp(shifted)
    return exp / np.sum(exp)
