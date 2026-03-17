# Data Model: CVCutter End-to-End Refactor

## Entity Relationship Overview

```text
ProcessingJob (1) ──< StageCheckpoint
ProcessingJob (1) ──< MediaSegmentCandidate
ProcessingJob (1) ──< AudioSourceProfile
ProcessingJob (1) ──< MetadataMappingRecord
ProcessingJob (1) ──< PublishingTask
ProcessingJob (1) ──< JobEventLedger
ProcessingJob (1) ──< JobDraftLock
ProcessingJob (1) ──< ConfigurationChangeRecord
ProcessingJob (1) ──< OperatorRolePolicy
```

## Entities

### 1) ProcessingJob

- **Purpose**: Canonical workflow aggregate for ingest/segment/sync/map/publish.
- **Primary Key**: `job_id` (UUID, immutable).
- **Core Fields**:
  - `job_id: UUID`
  - `state: enum[draft, ready, running, paused, resumable, failed, completed, canceled]`
  - `classification_strategy: enum[content_based, timestamp_based]`
  - `low_confidence_threshold: int (0-100, default 70)`
  - `input_video_path: str`
  - `input_audio_sources: list[str]`
  - `metadata_source_refs: object` (program/song list + strategy-specific metadata refs)
  - `output_prefs: object` (destination options, title overlay config)
  - `active_attempt: int`
  - `last_error_code: str|null`
  - `created_at, updated_at, started_at, ended_at: datetime`
- **Validation Rules**:
  - `classification_strategy` required before transition to `ready`.
  - Timestamp strategy requires valid recording-time metadata and event schedule metadata.
  - Unsupported I/O formats are rejected at validation stage.
  - Single active job policy: only one `running` job per workstation.
  - Executable workflow role is fixed to `operator`; editor/publisher remain descriptive labels only.

### 2) StageCheckpoint

- **Purpose**: Resume cursor and stage completion evidence.
- **Unique Key**: (`job_id`, `stage_name`, `attempt`).
- **Core Fields**:
  - `checkpoint_id: UUID`
  - `job_id: UUID`
  - `stage_name: enum[ingest, classify, segment_detect, sync, map_metadata, export, publish]`
  - `attempt: int >= 1`
  - `status: enum[pending, running, completed, failed, invalidated]`
  - `resume_cursor: object|null`
  - `input_fingerprint: str`
  - `output_fingerprint: str|null`
  - `created_at, completed_at: datetime|null`
- **Validation Rules**:
  - Duplicate (`job_id`, `stage_name`, `attempt`) must fail.
  - Resume is permitted only from first incomplete stage in current valid attempt chain.
  - Config mutations can invalidate downstream checkpoints via dependency map.

### 3) MediaSegmentCandidate

- **Purpose**: Proposed performance intervals for operator confirmation.
- **Core Fields**:
  - `segment_id: UUID`
  - `job_id: UUID`
  - `start_ms, end_ms: int`
  - `confidence_score: int (0-100)`
  - `requires_review: bool`
  - `review_status: enum[pending, accepted, adjusted, rejected]`
  - `modality_scores: object` (audio evidence, visual evidence)
  - `created_at, reviewed_at: datetime|null`
- **Validation Rules**:
  - `start_ms < end_ms`.
  - `requires_review = true` if `confidence_score < job.low_confidence_threshold`.
  - In modality disagreement cases, candidate set must retain confidence-weighted alternatives.
  - Export/publish must be blocked while any segment has `requires_review = true` and `review_status = pending`.

### 4) AudioSourceProfile

- **Purpose**: Synchronization parameters and validation per audio source.
- **Core Fields**:
  - `audio_profile_id: UUID`
  - `job_id: UUID`
  - `source_name: str`
  - `source_kind: enum[embedded_video, external]`
  - `offset_ms: int`
  - `gain_db: float`
  - `noise_reduction_level: float (0.0-1.0)`
  - `tuning_mode: enum[simple, waveform]`
  - `quality_status: enum[ok, flagged_manual_correction]`
  - `correction_resolution_status: enum[not_required, pending_correction, corrected]`
- **Validation Rules**:
  - Single-source embedded-only jobs auto-skip sync stage.
  - Single-source external-only jobs require manual sync confirmation.
  - Outputs with median alignment error > 80 ms are flagged.
  - Publish must be blocked while any output remains `flagged_manual_correction` until `correction_resolution_status = corrected`.

### 5) MetadataMappingRecord

- **Purpose**: Segment-to-publish metadata mapping outcome.
- **Core Fields**:
  - `mapping_id: UUID`
  - `job_id: UUID`
  - `segment_id: UUID`
  - `schema_version: str`
  - `title: str`
  - `description: str`
  - `tags: list[str]`
  - `publish_visibility: enum[public, unlisted, private]`
  - `source_trace: object` (program list row, transcript evidence, timestamp evidence)
  - `validation_status: enum[valid, invalid]`
- **Validation Rules**:
  - `schema_version` is required for every imported metadata payload.
  - Current and immediately previous schema versions are accepted.
  - Missing required publish metadata blocks publish stage.

### 6) PublishingTask

- **Purpose**: Track per-segment outbound delivery with dedup and retry safety.
- **Unique Key**: (`job_id`, `segment_id`, `destination`).
- **Core Fields**:
  - `publish_task_id: UUID`
  - `job_id: UUID`
  - `segment_id: UUID`
  - `destination: enum[youtube]`
  - `status: enum[pending, uploading, retry_waiting, completed, failed_manual_intervention]`
  - `attempt_count: int`
  - `first_transient_failure_at: datetime|null`
  - `next_retry_at: datetime|null`
  - `external_object_id: str|null`
  - `last_error_code: str|null`
- **Validation Rules**:
  - Non-approved destinations are rejected before external calls.
  - Retry window is capped at 15 minutes from first transient failure.
  - Idempotency/dedup rules block duplicate publish side effects.

### 7) JobEventLedger (Minimal Audit Ledger + Extended Events)

- **Purpose**: Immutable audit and structured observability records.
- **Core Fields**:
  - `event_id: UUID`
  - `event_schema_version: str`
  - `job_id: UUID|null`
  - `event_type: str`
  - `stage_name: str|null`
  - `attempt: int|null`
  - `severity: enum[info, warning, error]`
  - `payload: object`
  - `occurred_at: datetime`
  - `is_minimal_audit: bool`
- **Validation Rules**:
  - Minimal audit entries are non-deletable (job creation, stage transitions, retry outcomes, terminal outcome).
  - All core stages must emit start/completion/failure events.
  - `job_id` may be null only for system-level storage monitor events with no active job.

### 8) JobDraftLock

- **Purpose**: Exclusive edit lock for job drafts across app instances.
- **Core Fields**:
  - `lock_id: UUID`
  - `job_id: UUID`
  - `owner_instance_id: str`
  - `owner_display_name: str`
  - `locked_at: datetime`
  - `heartbeat_at: datetime`
  - `status: enum[active, stale, released]`
- **Validation Rules**:
  - Only one active lock per `job_id`.
  - Concurrent lock requests are rejected with lock-owner guidance.
  - Stale locks are transitioned safely during startup recovery flow.

### 9) ConfigurationChangeRecord

- **Purpose**: Track post-checkpoint config mutations and invalidation decisions.
- **Core Fields**:
  - `change_id: UUID`
  - `job_id: UUID`
  - `changed_fields: list[str]`
  - `dependency_impact: list[str]` (affected stages)
  - `decision: enum[invalidate_and_continue, cancel_resume]`
  - `confirmed_by_operator: bool`
  - `confirmed_at: datetime|null`
- **Validation Rules**:
  - Resume requires explicit operator decision when affected downstream stages exist.
  - Invalidation actions must append corresponding ledger events.

#### Configuration-to-Stage Dependency Map (Normative)

| Changed Field Group | Affected Stages | Required Operator Decision |
|---|---|---|
| `classification_strategy` | `classify`, `segment_detect`, `map_metadata`, `export`, `publish` | Invalidate affected checkpoints or cancel resume |
| `low_confidence_threshold` | `segment_detect`, `map_metadata`, `export`, `publish` | Invalidate affected checkpoints or cancel resume |
| `metadata_source_refs` (program/song list, event schedule, recording-time metadata) | `classify`, `map_metadata`, `publish` | Invalidate affected checkpoints or cancel resume |
| `input_video_path`, `input_audio_sources` | all processing stages | Invalidate all processing checkpoints or cancel resume |
| `output_prefs` (title overlay, destination profile) | `export`, `publish` | Invalidate affected checkpoints or cancel resume |
| Credentials / API version pin updates | `publish` and integration-dependent operations | Invalidate affected checkpoints or cancel resume |

Resume requests with impacted completed stages must be blocked until this decision is recorded.

## Classification Decision Rules (Normative)

- Confidence score range is `0-100`.
- A candidate is treated as confident only when:
  - top score `>= 70`, and
  - top score is at least `10` points above the next candidate.
- Single-candidate case is treated as confident when score `>= 70`.
- No-confident-match requires operator guidance flow:
  - switch strategy, and/or
  - adjust matching inputs.
- Timestamp strategy validity rules:
  - recording-time metadata must be present and parseable ISO 8601 with timezone,
  - event schedule metadata must provide derivable event-window bounds,
  - timestamp must fall within event bounds with `+/- 10 minute` tolerance,
  - otherwise classification is blocked with corrective guidance.

### 10) OperatorRolePolicy

- **Purpose**: Enforce FR-050 role normalization in workflow execution.
- **Core Fields**:
  - `policy_id: UUID`
  - `job_id: UUID`
  - `executable_role: enum[operator]`
  - `context_labels: list[editor, publisher]`
  - `recorded_at: datetime`
- **Validation Rules**:
  - Any role value other than `operator` for executable workflow actions is rejected.
  - `editor`/`publisher` labels are allowed only for UI/story context and must not branch authorization behavior.

## State Transitions

### ProcessingJob Lifecycle

- Normal flow: `draft -> ready -> running -> completed|failed|canceled`
- Interruption recovery flow: `running -> paused -> resumable -> running`
- Startup stale recovery: stale `running` with no worker process must transition via `paused` to `resumable` before new-job start
- Invalid transitions (example `completed -> running`) must be rejected with guidance

### PublishingTask Lifecycle

- `pending -> uploading -> completed`
- `uploading -> retry_waiting -> uploading` (until retry deadline)
- `uploading|retry_waiting -> failed_manual_intervention` (deadline exceeded or non-recoverable)

### JobDraftLock Lifecycle

- `active -> released`
- `active -> stale -> released` (recovery path)

## Integrity Constraints Summary

- `job_id` is immutable UUID.
- Checkpoint uniqueness: (`job_id`, `stage_name`, `attempt`).
- Publish dedup uniqueness: (`job_id`, `segment_id`, `destination`).
- One active workstation job at a time.
- Minimal audit ledger entries are protected from deletion.
- Executable authorization role is fixed to `operator`.
- Cleanup operations may delete non-audit records/artifacts only; minimal audit ledger classes remain non-deletable.
