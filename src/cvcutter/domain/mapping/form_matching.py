"""Deterministic weighted matching between segments and performer form responses."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cvcutter.domain.models.metadata import FormResponse, ProgramEntry
    from cvcutter.domain.models.segment import PerformanceSegment

_DEFAULT_MIN_FORM_SCORE = 0.35


def match_form_responses(
    segments: list[PerformanceSegment],
    entries: list[ProgramEntry],
    responses: list[FormResponse],
) -> dict[str, FormResponse]:
    """Match form responses to segments using weighted performer/title fuzzy scoring."""
    if not segments or not entries or not responses:
        return {}

    sorted_entries = sorted(entries, key=lambda entry: entry.order_number)
    sorted_segments = sorted(segments, key=lambda segment: segment.segment_index)
    available_responses = sorted(responses, key=lambda response: response.id)
    matched_by_segment: dict[str, FormResponse] = {}

    for segment in sorted_segments:
        entry = _entry_for_segment(segment, sorted_entries)
        if entry is None:
            continue

        best_index: int | None = None
        best_score = -1.0
        for response_index, response in enumerate(available_responses):
            score = _weighted_form_score(entry, response)
            if score < _DEFAULT_MIN_FORM_SCORE:
                continue
            if score > best_score:
                best_index = response_index
                best_score = score

        if best_index is None:
            continue

        matched_by_segment[str(segment.id)] = available_responses.pop(best_index)

    return matched_by_segment


def _entry_for_segment(segment: PerformanceSegment, entries: list[ProgramEntry]) -> ProgramEntry | None:
    if not entries:
        return None
    if 0 <= segment.segment_index < len(entries):
        return entries[segment.segment_index]
    return None


def _weighted_form_score(entry: ProgramEntry, response: FormResponse) -> float:
    title_score = _similarity(entry.piece_title, response.piece_title)
    performer_candidates = entry.performer_names or [entry.ensemble or "", entry.instrument or ""]
    performer_score = max(
        (_similarity(candidate, response.performer_name) for candidate in performer_candidates),
        default=0.0,
    )
    return (title_score * 0.6) + (performer_score * 0.4)


def _similarity(left: str, right: str) -> float:
    normalized_left = _normalize(left)
    normalized_right = _normalize(right)
    if not normalized_left or not normalized_right:
        return 0.0
    ratio = SequenceMatcher(None, normalized_left, normalized_right).ratio()
    containment = 1.0 if normalized_right in normalized_left or normalized_left in normalized_right else 0.0
    return max(ratio, containment)


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[^\w\sぁ-ゖァ-ヺ一-龯]", " ", text.casefold())
    return re.sub(r"\s+", "", cleaned).strip()
