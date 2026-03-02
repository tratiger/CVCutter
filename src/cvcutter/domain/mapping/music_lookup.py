"""Music-dictionary lookup signal extraction for mapping fusion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cvcutter.domain.models.metadata import MatchSignal
from cvcutter.shared.types import MatchSignalType

if TYPE_CHECKING:
    from cvcutter.domain.services.music_lookup import MusicLookupService


def lookup_match_signals(
    title: str,
    composer: str | None,
    lookup_service: MusicLookupService,
) -> list[MatchSignal]:
    """Query bundled music dictionary and return MUSIC_LOOKUP evidence signals."""
    if not title.strip():
        return []
    try:
        if not lookup_service.is_available():
            return []
        matches = lookup_service.lookup(title=title, composer=composer, performers=None)
    except Exception:
        return []

    signals: list[MatchSignal] = []
    for match in matches:
        confidence = _clamp(match.score)
        evidence = f"work:{match.work_id}|title:{match.title}|revision:{match.dictionary_revision}"
        if match.composer:
            evidence = f"{evidence}|composer:{match.composer}"
        signals.append(
            MatchSignal(
                signal_type=MatchSignalType.MUSIC_LOOKUP,
                confidence=confidence,
                evidence=evidence,
            ),
        )

    signals.sort(key=lambda signal: signal.confidence, reverse=True)
    return signals


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
