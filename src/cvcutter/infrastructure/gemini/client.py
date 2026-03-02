"""Gemini enrichment adapter with graceful non-throwing fallback behavior."""

from __future__ import annotations

import importlib
import json
import re
from typing import TYPE_CHECKING, Any

from cvcutter.domain.services.ai_enrichment import AIEnrichmentService

if TYPE_CHECKING:
    from pathlib import Path

    from cvcutter.domain.models.metadata import FormResponse, ProgramEntry
    from cvcutter.domain.models.segment import PerformanceSegment
    from cvcutter.domain.services.types import SuggestedMapping


class GeminiEnrichmentClient(AIEnrichmentService):
    """Optional Gemini-backed enrichment adapter that never raises on runtime failures."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
        model: Any | None = None,
    ) -> None:
        self._model = model if model is not None else _load_model(api_key=api_key, model_name=model_name)

    def parse_pdf(self, pdf_path: Path, local_entries: list[ProgramEntry]) -> list[ProgramEntry] | None:
        del local_entries
        model = self._model
        if model is None:
            return None
        try:
            prompt = (
                f"Extract structured concert program entries from: {pdf_path.name}. "
                "Return JSON only with schema: "
                '{"entries":[{"id":"...", "order_number":1, "piece_title":"...", "composer":"...", '
                '"performer_names":["..."], "ensemble":"...", "instrument":"...", "raw_text":"..."}]}.'
            )
            response = model.generate_content(prompt)
            payload = _parse_json_payload(getattr(response, "text", ""))
            if payload is None:
                return None
            entries = _entries_from_payload(payload)
            if entries is None:
                return None
            return entries
        except Exception:
            return None

    def match_form_responses(
        self,
        segments: list[PerformanceSegment],
        entries: list[ProgramEntry],
        responses: list[FormResponse],
    ) -> list[SuggestedMapping] | None:
        model = self._model
        if model is None:
            return None
        try:
            prompt = (
                "Match responses to entries. "
                f"segments={len(segments)} entries={len(entries)} responses={len(responses)}. "
                "Return JSON only with schema: "
                '{"mappings":[{"segment_id":"...", "program_entry_id":"...", "form_response_id":"...", '
                '"confidence":0.0, "reason":"..."}]}.'
            )
            response = model.generate_content(prompt)
            payload = _parse_json_payload(getattr(response, "text", ""))
            if not isinstance(payload, dict):
                return None
            suggestions = _suggestions_from_payload(payload)
            if suggestions is None:
                return None
            return suggestions
        except Exception:
            return None

    def is_available(self) -> bool:
        return self._model is not None


def _load_model(*, api_key: str | None, model_name: str) -> Any | None:
    if not api_key:
        return None
    try:
        module = importlib.import_module("google.generativeai")
    except Exception:
        return None
    configure = getattr(module, "configure", None)
    model_factory = getattr(module, "GenerativeModel", None)
    if not callable(configure) or model_factory is None:
        return None
    try:
        configure(api_key=api_key)
        return model_factory(model_name)
    except Exception:
        return None


def _parse_json_payload(raw_text: str) -> Any | None:
    text = str(raw_text).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced_match is None:
            return None
        try:
            return json.loads(fenced_match.group(1))
        except json.JSONDecodeError:
            return None


def _entries_from_payload(payload: Any) -> list[ProgramEntry] | None:
    from cvcutter.domain.models.metadata import ProgramEntry

    raw_entries: Any = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(raw_entries, list):
        return None

    entries: list[ProgramEntry] = []
    for index, raw_entry in enumerate(raw_entries, start=1):
        if not isinstance(raw_entry, dict):
            continue
        piece_title = str(raw_entry.get("piece_title") or raw_entry.get("title") or "").strip()
        if not piece_title:
            continue
        raw_order = raw_entry.get("order_number") or raw_entry.get("order") or index
        try:
            order_number = max(1, int(raw_order))
        except (TypeError, ValueError):
            order_number = index
        raw_performers = raw_entry.get("performer_names")
        if isinstance(raw_performers, list):
            performers = [str(item).strip() for item in raw_performers if str(item).strip()]
        else:
            performer_name = str(raw_entry.get("performer_name") or "").strip()
            performers = [performer_name] if performer_name else []

        entries.append(
            ProgramEntry(
                id=str(raw_entry.get("id") or f"gemini-{order_number:03d}"),
                order_number=order_number,
                piece_title=piece_title,
                composer=str(raw_entry.get("composer") or "").strip() or None,
                performer_names=performers,
                ensemble=str(raw_entry.get("ensemble") or "").strip() or None,
                instrument=str(raw_entry.get("instrument") or "").strip() or None,
                raw_text=str(raw_entry.get("raw_text") or piece_title),
            ),
        )
    return entries


def _suggestions_from_payload(payload: dict[str, Any]) -> list[SuggestedMapping] | None:
    from cvcutter.domain.services.types import SuggestedMapping

    raw_mappings = payload.get("mappings")
    if not isinstance(raw_mappings, list):
        return None

    suggestions: list[SuggestedMapping] = []
    for raw_mapping in raw_mappings:
        if not isinstance(raw_mapping, dict):
            continue
        segment_id = str(raw_mapping.get("segment_id") or "").strip()
        if not segment_id:
            continue
        confidence = _clamp(float(raw_mapping.get("confidence") or raw_mapping.get("score") or 0.0))
        suggestions.append(
            SuggestedMapping(
                segment_id=segment_id,
                program_entry_id=_optional_text(raw_mapping.get("program_entry_id")),
                form_response_id=_optional_text(raw_mapping.get("form_response_id")),
                confidence=confidence,
                reason=str(raw_mapping.get("reason") or "gemini-suggestion"),
            ),
        )
    return suggestions


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
