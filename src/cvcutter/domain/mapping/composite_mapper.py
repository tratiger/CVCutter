"""Composite metadata mapper combining sequential, transcription, form, and lookup signals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING
from uuid import uuid4

from cvcutter.domain.mapping.form_matching import match_form_responses
from cvcutter.domain.mapping.music_lookup import lookup_match_signals
from cvcutter.domain.mapping.transcription import extract_match_signals
from cvcutter.domain.models.metadata import (
    FormResponse,
    MatchSignal,
    ProgramEntry,
    VideoMetadataMapping,
)
from cvcutter.shared.types import MatchMethod, MatchSignalType, PrivacySetting

if TYPE_CHECKING:
    from cvcutter.domain.models.segment import PerformanceSegment
    from cvcutter.domain.services.music_lookup import MusicLookupService
    from cvcutter.domain.services.types import TranscriptionResult


@dataclass(frozen=True)
class MappingWeights:
    """Relative weights for each mapping evidence channel."""

    sequential: float = 0.35
    transcription: float = 0.35
    lookup: float = 0.2
    form: float = 0.1


class CompositeMapper:
    """Fuse multiple matching signals into final segment-to-metadata mappings."""

    def __init__(
        self,
        *,
        weights: MappingWeights | None = None,
        auto_verify_threshold: float = 0.8,
        minimum_match_confidence: float = 0.2,
    ) -> None:
        self._weights = weights or MappingWeights()
        self._auto_verify_threshold = _clamp(auto_verify_threshold)
        self._minimum_match_confidence = _clamp(minimum_match_confidence)

    def map_segments(
        self,
        segments: list[PerformanceSegment],
        entries: list[ProgramEntry],
        form_responses: list[FormResponse],
        transcription_results: list[TranscriptionResult] | dict[str, TranscriptionResult] | None,
        lookup_service: MusicLookupService,
    ) -> list[VideoMetadataMapping]:
        """Map detected segments to metadata entries using weighted multi-signal fusion."""
        sorted_segments = sorted(segments, key=lambda segment: segment.segment_index)
        sorted_entries = sorted(entries, key=lambda entry: entry.order_number)
        entry_by_id = {entry.id: entry for entry in sorted_entries}
        transcriptions_by_segment = self._coerce_transcriptions(sorted_segments, transcription_results)
        form_matches = match_form_responses(sorted_segments, sorted_entries, form_responses)
        mappings: list[VideoMetadataMapping] = []
        for segment in sorted_segments:
            segment_key = str(segment.id)
            sequential_entry = _entry_for_segment(segment, sorted_entries)
            matched_form = form_matches.get(segment_key)

            candidate_scores: dict[str, float] = {}
            candidate_signals: dict[str, list[MatchSignal]] = {}

            if sequential_entry is not None and self._weights.sequential > 0:
                sequential_signal = MatchSignal(
                    signal_type=MatchSignalType.SEQUENTIAL_ORDER,
                    confidence=1.0,
                    evidence=f"entry:{sequential_entry.id}|order:{sequential_entry.order_number}",
                )
                self._accumulate(candidate_scores, candidate_signals, sequential_entry.id, sequential_signal)

            transcription = transcriptions_by_segment.get(segment_key)
            if transcription is not None and self._weights.transcription > 0:
                for signal in extract_match_signals(transcription, sorted_entries):
                    entry_id = _entry_id_from_evidence(signal.evidence)
                    if entry_id is None or entry_id not in entry_by_id:
                        continue
                    self._accumulate(candidate_scores, candidate_signals, entry_id, signal)

            candidate_ids = set(candidate_scores)
            if not candidate_ids and sequential_entry is not None:
                candidate_ids.add(sequential_entry.id)

            if self._weights.lookup > 0:
                for entry_id in candidate_ids:
                    entry = entry_by_id[entry_id]
                    lookup_signals = lookup_match_signals(entry.piece_title, entry.composer, lookup_service)
                    if not lookup_signals:
                        continue
                    strongest = lookup_signals[0]
                    self._accumulate(
                        candidate_scores,
                        candidate_signals,
                        entry_id,
                        MatchSignal(
                            signal_type=MatchSignalType.MUSIC_LOOKUP,
                            confidence=strongest.confidence,
                            evidence=f"entry:{entry_id}|{strongest.evidence}",
                        ),
                    )

            if matched_form is not None and self._weights.form > 0:
                form_candidate_ids = set(entry_by_id) if entry_by_id else set(candidate_ids)
                for entry_id in form_candidate_ids:
                    confidence = _form_similarity(entry_by_id[entry_id], matched_form)
                    if confidence <= 0:
                        continue
                    self._accumulate(
                        candidate_scores,
                        candidate_signals,
                        entry_id,
                        MatchSignal(
                            signal_type=MatchSignalType.FORM_MATCH,
                            confidence=confidence,
                            evidence=f"entry:{entry_id}|response:{matched_form.id}",
                        ),
                    )

            if candidate_scores:
                best_entry_id, weighted_score = max(candidate_scores.items(), key=lambda item: item[1])
                selected_signals = candidate_signals.get(best_entry_id, [])
                active_weight = _active_weight(selected_signals, self._weights)
                confidence = _clamp(weighted_score / active_weight) if active_weight > 0 else 0.0
                top_signal_type = _strongest_signal_type(selected_signals, self._weights)
                match_method = _method_from_signal(top_signal_type)
                program_entry_id = best_entry_id if confidence >= self._minimum_match_confidence else None
            else:
                confidence = 0.0
                selected_signals = []
                match_method = MatchMethod.SEQUENTIAL
                program_entry_id = None

            selected_entry = entry_by_id.get(program_entry_id) if program_entry_id is not None else None
            mappings.append(
                VideoMetadataMapping(
                    id=uuid4(),
                    segment_id=segment_key,
                    program_entry_id=program_entry_id,
                    form_response_id=matched_form.id if matched_form is not None else None,
                    match_confidence=confidence,
                    match_method=match_method,
                    match_signals=selected_signals,
                    user_verified=confidence >= self._auto_verify_threshold,
                    final_title=_build_title(selected_entry, matched_form),
                    final_description=_build_description(selected_entry, matched_form),
                    final_privacy=(
                        matched_form.privacy_preference if matched_form is not None else PrivacySetting.PUBLIC
                    ),
                ),
            )

        return mappings

    def _accumulate(
        self,
        candidate_scores: dict[str, float],
        candidate_signals: dict[str, list[MatchSignal]],
        entry_id: str,
        signal: MatchSignal,
    ) -> None:
        weight = _weight_for_signal(signal.signal_type, self._weights)
        candidate_scores[entry_id] = candidate_scores.get(entry_id, 0.0) + (weight * signal.confidence)
        candidate_signals.setdefault(entry_id, []).append(signal)

    @staticmethod
    def _coerce_transcriptions(
        segments: list[PerformanceSegment],
        transcription_results: list[TranscriptionResult] | dict[str, TranscriptionResult] | None,
    ) -> dict[str, TranscriptionResult]:
        if transcription_results is None:
            return {}
        if isinstance(transcription_results, dict):
            return {str(key): value for key, value in transcription_results.items()}
        return {
            str(segment.id): transcription
            for segment, transcription in zip(segments, transcription_results, strict=False)
        }


def _entry_for_segment(segment: PerformanceSegment, entries: list[ProgramEntry]) -> ProgramEntry | None:
    if not entries:
        return None
    if 0 <= segment.segment_index < len(entries):
        return entries[segment.segment_index]
    return None


def _weight_for_signal(signal_type: MatchSignalType, weights: MappingWeights) -> float:
    if signal_type == MatchSignalType.SEQUENTIAL_ORDER:
        return weights.sequential
    if signal_type == MatchSignalType.TRANSCRIPTION:
        return weights.transcription
    if signal_type == MatchSignalType.MUSIC_LOOKUP:
        return weights.lookup
    return weights.form


def _strongest_signal_type(signals: list[MatchSignal], weights: MappingWeights) -> MatchSignalType:
    if not signals:
        return MatchSignalType.SEQUENTIAL_ORDER
    weighted_signal, signal_type = max(
        (
            (_weight_for_signal(signal.signal_type, weights) * signal.confidence, signal.signal_type)
            for signal in signals
        ),
        key=lambda item: item[0],
    )
    if weighted_signal <= 0:
        return MatchSignalType.SEQUENTIAL_ORDER
    return signal_type


def _method_from_signal(signal_type: MatchSignalType) -> MatchMethod:
    if signal_type == MatchSignalType.TRANSCRIPTION:
        return MatchMethod.TRANSCRIPTION
    if signal_type == MatchSignalType.MUSIC_LOOKUP:
        return MatchMethod.LOOKUP
    if signal_type == MatchSignalType.FORM_MATCH:
        return MatchMethod.FORM
    return MatchMethod.SEQUENTIAL


def _active_weight(signals: list[MatchSignal], weights: MappingWeights) -> float:
    if not signals:
        return 0.0
    signal_types = {signal.signal_type for signal in signals}
    return sum(_weight_for_signal(signal_type, weights) for signal_type in signal_types)


def _entry_id_from_evidence(evidence: str) -> str | None:
    for token in evidence.split("|"):
        if token.startswith("entry:"):
            return token.split(":", 1)[1]
    return None


def _form_similarity(entry: ProgramEntry, response: FormResponse) -> float:
    title_score = _string_similarity(entry.piece_title, response.piece_title)
    performer_candidates = entry.performer_names or [entry.ensemble or "", entry.instrument or ""]
    performer_score = max(
        (_string_similarity(name, response.performer_name) for name in performer_candidates),
        default=0.0,
    )
    return _clamp((title_score * 0.6) + (performer_score * 0.4))


def _string_similarity(left: str, right: str) -> float:
    normalized_left = _normalize_match_text(left)
    normalized_right = _normalize_match_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    ratio = SequenceMatcher(None, normalized_left, normalized_right).ratio()
    containment = 1.0 if normalized_right in normalized_left or normalized_left in normalized_right else 0.0
    return max(ratio, containment)


def _normalize_match_text(text: str) -> str:
    cleaned = re.sub(r"[^\w\sぁ-ゖァ-ヺ一-龯]", " ", text.casefold())
    return re.sub(r"\s+", "", cleaned).strip()


def _build_title(entry: ProgramEntry | None, form_response: FormResponse | None) -> str:
    if entry is None and form_response is None:
        return ""
    if entry is None and form_response is not None:
        return form_response.piece_title

    assert entry is not None
    performer_name = ""
    if form_response is not None and form_response.display_name_override:
        performer_name = form_response.display_name_override.strip()
    elif entry.performer_names:
        performer_name = entry.performer_names[0]

    if performer_name:
        return f"{entry.piece_title} - {performer_name}"
    return entry.piece_title


def _build_description(entry: ProgramEntry | None, form_response: FormResponse | None) -> str:
    parts: list[str] = []
    if entry is not None:
        if entry.composer:
            parts.append(f"Composer: {entry.composer}")
        if entry.performer_names:
            parts.append(f"Performer: {', '.join(entry.performer_names)}")
    if form_response is not None and form_response.custom_description:
        parts.append(form_response.custom_description.strip())
    return "\n".join(part for part in parts if part)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
