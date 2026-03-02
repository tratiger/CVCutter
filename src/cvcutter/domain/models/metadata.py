from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cvcutter.shared.types import MatchMethod, MatchSignalType, PrivacySetting

if TYPE_CHECKING:
    from uuid import UUID

DEFAULT_MAPPING_REVIEW_THRESHOLD = 0.8


@dataclass(frozen=True)
class MatchSignal:
    """Single signal contribution used to derive metadata match confidence."""

    signal_type: MatchSignalType
    confidence: float
    evidence: str

    def __post_init__(self) -> None:
        """Validate confidence bounds."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass
class ProgramEntry:
    """Program metadata parsed from the concert program source."""

    id: str
    order_number: int
    piece_title: str
    composer: str | None
    performer_names: list[str]
    ensemble: str | None
    instrument: str | None
    raw_text: str

    def __post_init__(self) -> None:
        """Validate required program entry fields."""
        if self.order_number < 1:
            raise ValueError("order_number must be >= 1")
        if not self.piece_title.strip():
            raise ValueError("piece_title must not be empty")


@dataclass
class FormResponse:
    """Performer-submitted metadata used for upload personalization."""

    id: str
    performer_name: str
    piece_title: str
    privacy_preference: PrivacySetting = PrivacySetting.PUBLIC
    display_name_override: str | None = None
    custom_description: str | None = None
    raw_data: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate required performer response fields."""
        if not self.performer_name.strip():
            raise ValueError("performer_name must not be empty")
        if not self.piece_title.strip():
            raise ValueError("piece_title must not be empty")


@dataclass
class VideoMetadataMapping:
    """Resolved mapping between a segment and metadata sources for upload."""

    id: UUID
    segment_id: str
    program_entry_id: str | None
    form_response_id: str | None
    match_confidence: float
    match_method: MatchMethod
    match_signals: list[MatchSignal]
    user_verified: bool = False
    final_title: str = ""
    final_description: str = ""
    final_privacy: PrivacySetting = PrivacySetting.PUBLIC
    final_category_id: str = "10"
    final_tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate confidence bounds and required segment identifier."""
        if not self.segment_id.strip():
            raise ValueError("segment_id must not be empty")
        if not 0.0 <= self.match_confidence <= 1.0:
            raise ValueError("match_confidence must be between 0.0 and 1.0")

    def is_ready_for_upload(self, review_threshold: float = DEFAULT_MAPPING_REVIEW_THRESHOLD) -> bool:
        """Return True when required upload metadata and verification gates are satisfied."""
        has_mapping_or_manual_confirmation = bool(self.program_entry_id) or self.user_verified
        if not has_mapping_or_manual_confirmation:
            return False

        if not self.final_title.strip() or not self.final_description.strip():
            return False

        return not (self.match_confidence < review_threshold and not self.user_verified)
