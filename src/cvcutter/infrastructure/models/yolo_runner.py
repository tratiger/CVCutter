"""Ultralytics YOLO runner implementing the visual detector protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cvcutter.domain.services.types import Detection, VideoFrame


class YoloModelRunner:
    """Run YOLOv8 inference for one frame at a time."""

    def __init__(
        self,
        *,
        model_path: Path | str = Path("yolov8n.pt"),
        confidence_threshold: float = 0.25,
        device: str | None = None,
    ) -> None:
        if confidence_threshold < 0 or confidence_threshold > 1:
            raise ValueError("confidence_threshold must be between 0 and 1.")
        self._model_path = Path(model_path)
        if not self._model_path.exists():
            raise FileNotFoundError(f"YOLO model file not found: {self._model_path}")

        try:
            import ultralytics
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("ultralytics is required for YOLO detection.") from exc
        yolo_class = getattr(ultralytics, "YOLO", None)
        if yolo_class is None:  # pragma: no cover - defensive fallback
            raise RuntimeError("ultralytics YOLO class is unavailable.")

        self._confidence_threshold = confidence_threshold
        self._device = device
        self._model = yolo_class(str(self._model_path))

    def detect(self, frame: VideoFrame) -> list[Detection]:
        """Run YOLO inference for a single frame."""
        try:
            predictions = self._model.predict(
                source=frame.data,
                conf=self._confidence_threshold,
                verbose=False,
                device=self._device,
            )
            if not predictions:
                return []

            result = predictions[0]
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                return []

            names_raw = getattr(self._model, "names", {})
            names: dict[int, str]
            if isinstance(names_raw, dict):
                names = {int(key): str(value) for key, value in names_raw.items()}
            else:
                names = {index: str(value) for index, value in enumerate(names_raw)}

            detections: list[Detection] = []
            for box in boxes:
                class_id = int(_scalar(box.cls))
                confidence = float(_scalar(box.conf))
                xyxy_values = _to_list(box.xyxy)
                if len(xyxy_values) < 4:
                    continue
                detections.append(
                    Detection(
                        class_name=names.get(class_id, str(class_id)),
                        confidence=confidence,
                        bbox=(
                            float(xyxy_values[0]),
                            float(xyxy_values[1]),
                            float(xyxy_values[2]),
                            float(xyxy_values[3]),
                        ),
                    ),
                )
            return detections
        except Exception as exc:
            raise RuntimeError("YOLO inference failed.") from exc

    def model_version(self) -> str:
        """Return deterministic model identifier for checkpointing."""
        return f"yolo:{self._model_path.name}"


def _scalar(value: Any) -> float:
    if hasattr(value, "item"):
        return float(value.item())
    if isinstance(value, (list, tuple)):
        if not value:
            return 0.0
        return _scalar(value[0])
    try:
        return float(value[0])
    except Exception:
        return float(value)


def _to_list(value: Any) -> list[float]:
    if hasattr(value, "tolist"):
        converted = value.tolist()
        if converted and isinstance(converted[0], list):
            return [float(item) for item in converted[0]]
        return [float(item) for item in converted]
    if isinstance(value, list):
        if value and isinstance(value[0], list):
            return [float(item) for item in value[0]]
        return [float(item) for item in value]
    if isinstance(value, tuple):
        return [float(item) for item in value]
    return []
