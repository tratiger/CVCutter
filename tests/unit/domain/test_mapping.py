"""Unit tests for mapping signal fusion and deterministic matching behavior (T048)."""

from __future__ import annotations

from uuid import uuid4

from cvcutter.domain.mapping import (
    CompositeMapper,
    MappingWeights,
    extract_match_signals,
    match_form_responses,
    normalize_program_entries,
)
from cvcutter.domain.models.metadata import FormResponse, ProgramEntry
from cvcutter.domain.models.segment import PerformanceSegment
from cvcutter.domain.services.types import MusicLookupMatch, PdfTextBlock, TranscriptionResult
from cvcutter.shared.types import MatchMethod, MatchSignalType, PrivacySetting


class _StubLookupService:
    def __init__(self, *, matches: list[MusicLookupMatch] | None = None) -> None:
        self._matches = list(matches or [])

    def lookup(
        self,
        title: str,
        composer: str | None = None,
        performers: list[str] | None = None,
    ) -> list[MusicLookupMatch]:
        del title, composer, performers
        return list(self._matches)

    def is_available(self) -> bool:
        return True

    def dictionary_revision(self) -> str:
        return "test-revision"


def _entry(
    order: int,
    *,
    title: str,
    composer: str | None = None,
    performers: list[str] | None = None,
) -> ProgramEntry:
    return ProgramEntry(
        id=f"entry-{order}",
        order_number=order,
        piece_title=title,
        composer=composer,
        performer_names=list(performers or []),
        ensemble=None,
        instrument=None,
        raw_text=f"{order}. {title}",
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


def test_transcription_matching_finds_program_entry_by_title() -> None:
    entries = [
        _entry(1, title="月光ソナタ", composer="ベートーヴェン"),
        _entry(2, title="ノクターン 作品9-2", composer="ショパン"),
    ]
    transcription = TranscriptionResult(
        text="次はベートーヴェンの月光ソナタを演奏します",
        segments=[],
        language="ja",
        confidence=0.9,
    )

    signals = extract_match_signals(transcription, entries)

    assert signals
    assert signals[0].signal_type == MatchSignalType.TRANSCRIPTION
    assert "entry:entry-1" in signals[0].evidence


def test_sequential_order_maps_segment_index_to_program_order() -> None:
    entries = [
        _entry(1, title="Piece A"),
        _entry(2, title="Piece B"),
    ]
    segments = [_segment(0), _segment(1)]
    mapper = CompositeMapper(weights=MappingWeights(sequential=1.0, transcription=0.0, lookup=0.0, form=0.0))

    mappings = mapper.map_segments(
        segments=segments,
        entries=entries,
        form_responses=[],
        transcription_results=[],
        lookup_service=_StubLookupService(),
    )

    assert [mapping.program_entry_id for mapping in mappings] == ["entry-1", "entry-2"]
    assert all(mapping.match_method == MatchMethod.SEQUENTIAL for mapping in mappings)


def test_lookup_signal_increases_fused_confidence() -> None:
    entries = [_entry(1, title="Symphony No.5", composer="Beethoven")]
    segments = [_segment(0)]
    mapper = CompositeMapper(weights=MappingWeights(sequential=0.0, transcription=0.2, lookup=0.8, form=0.0))
    lookup_match = MusicLookupMatch(
        work_id="work-1",
        title="Symphony No.5",
        composer="Beethoven",
        performers=[],
        score=1.0,
        dictionary_revision="dict-v1",
    )

    without_lookup = mapper.map_segments(
        segments=segments,
        entries=entries,
        form_responses=[],
        transcription_results=[
            TranscriptionResult(
                text="Symphony No.5",
                segments=[],
                language="en",
                confidence=0.2,
            ),
        ],
        lookup_service=_StubLookupService(matches=[]),
    )[0]
    with_lookup = mapper.map_segments(
        segments=segments,
        entries=entries,
        form_responses=[],
        transcription_results=[
            TranscriptionResult(
                text="Symphony No.5",
                segments=[],
                language="en",
                confidence=0.2,
            ),
        ],
        lookup_service=_StubLookupService(matches=[lookup_match]),
    )[0]

    assert with_lookup.match_confidence > without_lookup.match_confidence
    assert with_lookup.match_method == MatchMethod.LOOKUP


def test_composite_mapper_prefers_transcription_method_when_signal_is_strongest() -> None:
    entries = [_entry(1, title="クラールドリュヌ", composer="ドビュッシー")]
    segments = [_segment(0)]
    mapper = CompositeMapper(weights=MappingWeights(sequential=0.1, transcription=0.9, lookup=0.0, form=0.0))

    mappings = mapper.map_segments(
        segments=segments,
        entries=entries,
        form_responses=[],
        transcription_results=[
            TranscriptionResult(
                text="ドビュッシーのクラールドリュヌです",
                segments=[],
                language="ja",
                confidence=0.95,
            ),
        ],
        lookup_service=_StubLookupService(),
    )

    assert mappings[0].match_method == MatchMethod.TRANSCRIPTION


def test_confidence_threshold_controls_user_verification_flag() -> None:
    mapper = CompositeMapper(auto_verify_threshold=0.75)

    unmatched = mapper.map_segments(
        segments=[_segment(0)],
        entries=[],
        form_responses=[],
        transcription_results=[],
        lookup_service=_StubLookupService(),
    )[0]
    confident = mapper.map_segments(
        segments=[_segment(0)],
        entries=[_entry(1, title="エチュード 作品10 第1番", composer="ショパン")],
        form_responses=[],
        transcription_results=[
            TranscriptionResult(
                text="ショパンのエチュード作品10の1番",
                segments=[],
                language="ja",
                confidence=0.95,
            ),
        ],
        lookup_service=_StubLookupService(),
    )[0]

    assert unmatched.user_verified is False
    assert confident.user_verified is True


def test_form_response_weighted_matching_uses_name_and_piece_similarity() -> None:
    entries = [
        _entry(1, title="月光ソナタ", performers=["田中 太郎"]),
        _entry(2, title="ノクターン", performers=["鈴木 花子"]),
    ]
    segments = [_segment(0), _segment(1)]
    responses = [
        FormResponse(
            id="form-1",
            performer_name="田中太郎",
            piece_title="月光",
            privacy_preference=PrivacySetting.UNLISTED,
        ),
        FormResponse(
            id="form-2",
            performer_name="鈴木花子",
            piece_title="ノクターン",
            privacy_preference=PrivacySetting.PUBLIC,
        ),
    ]

    matched = match_form_responses(segments, entries, responses)

    assert matched[str(segments[0].id)].id == "form-1"
    assert matched[str(segments[1].id)].id == "form-2"


def test_pdf_normalization_handles_split_numbered_lines_and_spaced_composer_prefix() -> None:
    entries = normalize_program_entries(
        [
            PdfTextBlock(
                text="1.\nComposer : Beethoven\nMoonlight Sonata\n2. Prelude - Op.28 No.4",
                page_number=1,
                block_index=1,
            ),
        ],
    )

    assert len(entries) == 2
    assert entries[0].composer == "Beethoven"
    assert entries[0].piece_title == "Moonlight Sonata"
    assert entries[1].composer is None
    assert entries[1].piece_title == "Prelude - Op.28 No.4"


def test_pdf_normalization_generates_unique_entry_ids_for_duplicate_order_numbers() -> None:
    entries = normalize_program_entries(
        [PdfTextBlock(text="1. First Piece\n1. Second Piece", page_number=1, block_index=1)],
    )

    assert len(entries) == 2
    assert len({entry.id for entry in entries}) == 2


def test_form_matching_can_select_entry_outside_sequential_candidate_set() -> None:
    entries = [
        _entry(1, title="Piece A", performers=["Performer A"]),
        _entry(2, title="Piece B", performers=["Performer B"]),
    ]
    segment = _segment(0)
    response = FormResponse(
        id="form-1",
        performer_name="Performer B",
        piece_title="Piece B",
        privacy_preference=PrivacySetting.PUBLIC,
    )
    mapper = CompositeMapper(
        minimum_match_confidence=0.0,
        weights=MappingWeights(sequential=0.1, transcription=0.0, lookup=0.0, form=0.9),
    )

    mapping = mapper.map_segments(
        segments=[segment],
        entries=entries,
        form_responses=[response],
        transcription_results=[],
        lookup_service=_StubLookupService(),
    )[0]

    assert mapping.program_entry_id == "entry-2"
