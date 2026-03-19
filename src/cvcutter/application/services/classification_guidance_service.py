from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TypedDict

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


class CandidateTrace(TypedDict):
    candidate_label: str
    candidate_text: str
    overlap_tokens: list[str]
    score: int


class ClassificationGuidanceService:
    def guide(self, scores: list[tuple[str, int]]) -> MatchResult:
        return evaluate_scores(scores)

    def guide_from_transcript(
        self,
        transcript_text: str,
        program_catalog: Sequence[dict[str, object] | str],
    ) -> MatchResult:
        transcript_tokens = _tokenize(transcript_text)
        candidate_trace: list[CandidateTrace] = []
        scored: list[tuple[str, int]] = []
        for candidate in program_catalog:
            label, candidate_text = _candidate_text(candidate)
            candidate_tokens = _tokenize(candidate_text)
            if not candidate_tokens:
                continue
            overlap = len(transcript_tokens & candidate_tokens)
            score = int(round((overlap / len(candidate_tokens)) * 100))
            scored.append((label, score))
            candidate_trace.append(
                {
                    "candidate_label": label,
                    "candidate_text": candidate_text,
                    "overlap_tokens": sorted(transcript_tokens & candidate_tokens),
                    "score": score,
                }
            )
        result = evaluate_scores(scored)
        top_trace = next(
            (trace for trace in candidate_trace if trace["candidate_label"] == result.top_candidate),
            None,
        )
        transcript_excerpt = transcript_text.strip()
        if len(transcript_excerpt) > 200:
            transcript_excerpt = f"{transcript_excerpt[:200]}..."
        result.trace_context = {
            **result.trace_context,
            "transcript_excerpt": transcript_excerpt,
            "transcript_tokens": sorted(transcript_tokens),
            "candidate_trace": sorted(candidate_trace, key=lambda item: item["score"], reverse=True),
            "matched_candidate_reference": top_trace,
        }
        return result
