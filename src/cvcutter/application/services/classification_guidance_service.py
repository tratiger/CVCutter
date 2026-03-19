from __future__ import annotations

import re
from collections.abc import Sequence

from cvcutter.domain.classification.confidence_policy import MatchResult, evaluate_scores


def _tokenize(value: str) -> set[str]:
    return {token for token in re.split(r"\W+", value.lower()) if token}


def _candidate_text(candidate: dict[str, object] | str) -> tuple[str, str]:
    if isinstance(candidate, str):
        return candidate, candidate
    title = str(candidate.get("segment_title", "")).strip()
    program_id = str(candidate.get("program_id", "")).strip()
    performer = str(candidate.get("performer_display_name", "")).strip()
    label = title or program_id or "unknown"
    return label, " ".join(part for part in (title, program_id, performer) if part)


class ClassificationGuidanceService:
    def guide(self, scores: list[tuple[str, int]]) -> MatchResult:
        return evaluate_scores(scores)

    def guide_from_transcript(
        self,
        transcript_text: str,
        program_catalog: Sequence[dict[str, object] | str],
    ) -> MatchResult:
        transcript_tokens = _tokenize(transcript_text)
        scored: list[tuple[str, int]] = []
        for candidate in program_catalog:
            label, candidate_text = _candidate_text(candidate)
            candidate_tokens = _tokenize(candidate_text)
            if not candidate_tokens:
                continue
            overlap = len(transcript_tokens & candidate_tokens)
            score = int(round((overlap / len(candidate_tokens)) * 100))
            scored.append((label, score))
        return evaluate_scores(scored)
