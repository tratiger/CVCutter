"""Transcription-based signal extraction for metadata mapping."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from cvcutter.domain.models.metadata import MatchSignal, ProgramEntry
from cvcutter.shared.types import MatchSignalType

if TYPE_CHECKING:
    from cvcutter.domain.services.types import TranscriptionResult

_MIN_TRANSCRIPTION_CONFIDENCE = 0.12


def extract_match_signals(
    transcription: TranscriptionResult,
    entries: list[ProgramEntry],
) -> list[MatchSignal]:
    """Extract TRANSCRIPTION match signals for program entries from transcription text."""
    normalized_text = _normalize_text(transcription.text)
    if not normalized_text:
        return []

    signals: list[MatchSignal] = []
    confidence_weight = 0.6 + 0.4 * _clamp(transcription.confidence)
    for entry in entries:
        title_score = _similarity(normalized_text, _normalize_text(entry.piece_title))
        composer_score = _similarity(normalized_text, _normalize_text(entry.composer or ""))
        entry_score = max(title_score, (title_score * 0.75) + (composer_score * 0.25))
        signal_confidence = _clamp(entry_score * confidence_weight)
        if signal_confidence < _MIN_TRANSCRIPTION_CONFIDENCE:
            continue

        evidence = f"entry:{entry.id}|title:{entry.piece_title}"
        if entry.composer:
            evidence = f"{evidence}|composer:{entry.composer}"

        signals.append(
            MatchSignal(
                signal_type=MatchSignalType.TRANSCRIPTION,
                confidence=signal_confidence,
                evidence=evidence,
            ),
        )

    signals.sort(key=lambda signal: signal.confidence, reverse=True)
    return signals


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    ratio = SequenceMatcher(None, left, right).ratio()
    containment = 1.0 if right in left else 0.0
    return max(ratio, containment)


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^\w\sぁ-ゖァ-ヺ一-龯]", " ", text.casefold())
    return re.sub(r"\s+", "", cleaned).strip()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
