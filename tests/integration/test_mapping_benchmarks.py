"""Benchmark scaffolds for mapping accuracy targets (T115)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cvcutter.domain.mapping import CompositeMapper, MappingWeights
from cvcutter.domain.models.metadata import ProgramEntry
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.services.types import MusicLookupMatch, TranscriptionResult

pytestmark = [pytest.mark.benchmark, pytest.mark.slow]


class _LookupStub:
    def lookup(
        self,
        title: str,
        composer: str | None = None,
        performers: list[str] | None = None,
    ) -> list[MusicLookupMatch]:
        del title, composer, performers
        return []

    def is_available(self) -> bool:
        return True

    def dictionary_revision(self) -> str:
        return "bench"


def _entry(order: int, title: str) -> ProgramEntry:
    return ProgramEntry(
        id=f"entry-{order}",
        order_number=order,
        piece_title=title,
        composer=None,
        performer_names=[],
        ensemble=None,
        instrument=None,
        raw_text=title,
    )


def _segment(index: int) -> PerformanceSegment:
    return PerformanceSegment(
        id=uuid4(),
        segment_index=index,
        start_time_seconds=float(index * 60),
        end_time_seconds=float(index * 60 + 45),
        detection_confidence=0.9,
        effective_detection_mode="full",
        detection_signals=[],
    )


def _accuracy(predicted: list[str | None], expected: list[str]) -> float:
    correct = sum(1 for got, want in zip(predicted, expected, strict=True) if got == want)
    return correct / len(expected)


def test_mapping_accuracy_sc003_scaffold() -> None:
    entries = [_entry(1, "Moonlight Sonata"), _entry(2, "Nocturne"), _entry(3, "Hungarian Rhapsody")]
    segments = [_segment(0), _segment(1), _segment(2)]
    transcriptions = [
        TranscriptionResult(text="Moonlight Sonata", segments=[], language="en", confidence=0.95),
        TranscriptionResult(text="Nocturne", segments=[], language="en", confidence=0.95),
        TranscriptionResult(text="Hungarian Rhapsody", segments=[], language="en", confidence=0.95),
    ]
    mapper = CompositeMapper(weights=MappingWeights(sequential=0.2, transcription=0.8, lookup=0.0, form=0.0))

    mappings = mapper.map_segments(
        segments=segments,
        entries=entries,
        form_responses=[],
        transcription_results=transcriptions,
        lookup_service=_LookupStub(),
    )
    accuracy = _accuracy(
        [mapping.program_entry_id for mapping in mappings],
        [entry.id for entry in entries],
    )

    assert accuracy >= 0.8


def test_sequential_mapping_accuracy_us4_as2_scaffold() -> None:
    entries = [_entry(index + 1, f"Piece {index + 1}") for index in range(10)]
    segments = [_segment(index) for index in range(10)]
    mapper = CompositeMapper(weights=MappingWeights(sequential=1.0, transcription=0.0, lookup=0.0, form=0.0))

    mappings = mapper.map_segments(
        segments=segments,
        entries=entries,
        form_responses=[],
        transcription_results=[],
        lookup_service=_LookupStub(),
    )
    accuracy = _accuracy(
        [mapping.program_entry_id for mapping in mappings],
        [entry.id for entry in entries],
    )

    assert accuracy >= 0.9
