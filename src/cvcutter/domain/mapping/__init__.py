"""Domain-level metadata mapping primitives and orchestration helpers."""

from __future__ import annotations

from cvcutter.domain.mapping.composite_mapper import CompositeMapper, MappingWeights
from cvcutter.domain.mapping.form_matching import match_form_responses
from cvcutter.domain.mapping.music_lookup import lookup_match_signals
from cvcutter.domain.mapping.pdf_extraction import normalize_program_entries
from cvcutter.domain.mapping.transcription import extract_match_signals

__all__ = [
    "CompositeMapper",
    "MappingWeights",
    "extract_match_signals",
    "lookup_match_signals",
    "match_form_responses",
    "normalize_program_entries",
]
