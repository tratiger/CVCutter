"""Integration scaffold for detect-to-mapping workflow behavior (T050)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cvcutter.domain.mapping import CompositeMapper, MappingWeights, normalize_program_entries
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.services.types import MusicLookupMatch, PdfTextBlock, TranscriptionResult

pytestmark = pytest.mark.integration


class _NoopLookupService:
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
        return "none"


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


def test_detect_to_mapping_workflow_scaffold() -> None:
    text_blocks = [
        PdfTextBlock(
            text="1. Beethoven: Symphony No.5\n2. Chopin: Nocturne Op.9 No.2",
            page_number=1,
            block_index=0,
        ),
    ]
    entries = normalize_program_entries(text_blocks)
    segments = [_segment(0), _segment(1)]
    transcriptions = [
        TranscriptionResult(
            text="ベートーヴェンの交響曲第5番です",
            segments=[],
            language="ja",
            confidence=0.9,
        ),
        TranscriptionResult(
            text="ショパンのノクターンを演奏します",
            segments=[],
            language="ja",
            confidence=0.9,
        ),
    ]
    mapper = CompositeMapper(weights=MappingWeights(sequential=0.3, transcription=0.7, lookup=0.0, form=0.0))

    mappings = mapper.map_segments(
        segments=segments,
        entries=entries,
        form_responses=[],
        transcription_results=transcriptions,
        lookup_service=_NoopLookupService(),
    )

    assert len(mappings) == 2
    assert all(mapping.program_entry_id is not None for mapping in mappings)
