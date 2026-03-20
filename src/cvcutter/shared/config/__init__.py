from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    classification_strategy: str = "content_based"
    low_confidence_threshold: int = 70
    publish_destination: str = "youtube"
    title_overlay_enabled: bool = False
    title_duration_seconds: int = 0


def _parse_bool(raw: str | int | bool | None, *, default: bool) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        if raw in {0, 1}:
            return raw == 1
        raise ValueError("title_overlay_enabled must be 0 or 1 when provided as integer")
    if not isinstance(raw, str):
        raise ValueError("title_overlay_enabled must be a boolean-like value")
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("title_overlay_enabled must be a boolean-like value")


def _parse_int(raw: str | int | None, *, default: int, field_name: str) -> int:
    if raw is None:
        return default
    if isinstance(raw, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        return int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an integer") from error


def load_runtime_config(values: Mapping[str, str | int | bool] | None) -> RuntimeConfig:
    source: Mapping[str, str | int | bool] = values or {}
    classification_strategy = str(source.get("classification_strategy", "content_based")).strip().lower()
    if classification_strategy not in {"content_based", "timestamp_based"}:
        raise ValueError("classification_strategy must be content_based or timestamp_based")

    low_confidence_threshold = _parse_int(
        source.get("low_confidence_threshold"),
        default=70,
        field_name="low_confidence_threshold",
    )
    if low_confidence_threshold < 0 or low_confidence_threshold > 100:
        raise ValueError("low_confidence_threshold must be between 0 and 100")

    publish_destination = str(source.get("publish_destination", "youtube")).strip().lower()
    if publish_destination != "youtube":
        raise ValueError("publish_destination must be youtube")

    title_overlay_enabled = _parse_bool(
        source.get("title_overlay_enabled"),
        default=False,
    )
    title_duration_seconds = _parse_int(
        source.get("title_duration_seconds"),
        default=0,
        field_name="title_duration_seconds",
    )
    if title_duration_seconds < 0:
        raise ValueError("title_duration_seconds must be >= 0")

    return RuntimeConfig(
        classification_strategy=classification_strategy,
        low_confidence_threshold=low_confidence_threshold,
        publish_destination=publish_destination,
        title_overlay_enabled=title_overlay_enabled,
        title_duration_seconds=title_duration_seconds,
    )
