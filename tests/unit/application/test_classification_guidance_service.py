from __future__ import annotations

from cvcutter.application.services.classification_guidance_service import ClassificationGuidanceService


def test_classification_guidance_matches_transcript_to_catalog() -> None:
    service = ClassificationGuidanceService()
    result = service.guide_from_transcript(
        "Tonight performer A plays song river lights",
        [
            {"program_id": "P1", "segment_title": "River Lights", "performer_display_name": "Performer A"},
            {"program_id": "P2", "segment_title": "Ocean Breeze", "performer_display_name": "Performer B"},
        ],
    )

    assert result.top_candidate == "River Lights"
    assert result.confidence_state in {"confident", "no_confident_match"}


def test_classification_guidance_handles_empty_catalog() -> None:
    service = ClassificationGuidanceService()
    result = service.guide_from_transcript("any transcript", [])
    assert result.confidence_state == "no_confident_match"
    assert "no_candidates" in result.reason_codes
