# Contract: Classification Decision Rules

## Scope

Defines deterministic behavior for classification confidence, fallback flow, and timestamp-strategy validity checks.

## Strategy Persistence Contract (FR-019)

- Selected classification strategy is persisted per `job_id`.
- Strategy value is loaded on resume/restart and must match persisted job configuration.
- Strategy changes after checkpoint creation must trigger FR-021 invalidate-or-cancel flow.

## Content-Based Matching Contract (FR-019)

Content-based classification requires:

- Pre-performance speech transcription input (local model output).
- Program/song-list metadata as candidate catalog.
- Matching process that scores candidates and emits confidence values.
- Traceable source context containing:
  - transcript excerpt(s),
  - matched candidate reference(s),
  - scoring rationale/reason codes.

When transcription is unavailable, behavior must follow model-availability fallback/block rules (FR-028).

## Confidence Scoring Contract (FR-029)

- Score range: `0-100`.
- Confident classification requires:
  - top candidate score `>= 70`, and
  - margin `>= 10` points over the next candidate.
- Single-candidate case:
  - confident when top score `>= 70`.

## No-Confident-Match Contract (FR-026)

When confidence conditions are not met:

1. Classifier output is marked `no_confident_match`.
2. Operator receives guided fallback actions:
   - switch strategy (`content_based <-> timestamp_based`)
   - adjust matching inputs and retry
3. Workflow cannot silently continue as confident classification.

## Timestamp Strategy Validity Contract (FR-034)

Timestamp-based classification requires:

- Recording-time metadata with required fields and parseable ISO 8601 timestamp including timezone.
- Event schedule metadata with derivable start/end event bounds.
- Recording timestamp within event bounds using `+/- 10 minute` tolerance.

If any condition fails, classification is blocked with remediation guidance.

## Output Contract

Classifier output payload includes:

- `strategy`
- `top_candidate`
- `top_score`
- `next_score` (nullable for single-candidate case)
- `confidence_state` (`confident` | `no_confident_match` | `blocked_invalid_metadata`)
- `reason_codes`
- `trace_context`
