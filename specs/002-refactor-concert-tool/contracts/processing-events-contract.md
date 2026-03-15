# Contract: Processing Event Stream

## Scope

Defines structured event records emitted for observability, audit, and resume/retry diagnostics.

## Transport

- Local append-only event store (for example JSONL or SQLite-backed event table)
- Event schema is stable and versioned (`event_schema_version`)

## Event Envelope

```json
{
  "event_id": "uuid",
  "event_schema_version": "1",
  "job_id": "uuid|null",
  "event_type": "stage.started",
  "occurred_at": "2026-03-14T23:49:01Z",
  "severity": "info",
  "stage_name": "sync",
  "attempt": 1,
  "payload": {}
}
```

## Required Event Types

- `job.created`
- `job.state_changed`
- `stage.started`
- `stage.completed`
- `stage.failed`
- `retry.scheduled`
- `retry.completed`
- `retry.escalated_manual`
- `publish.dedup_blocked`
- `storage.threshold_warning`
- `storage.threshold_block`
- `storage.threshold_pause`
- `cleanup.performed`
- `cleanup.rejected`

## Validation Rules

- Core stages must emit start/completion/failure triplet semantics.
- Every retry scheduling action must include planned delay, reason, and deadline context.
- Every terminal job outcome must be represented (`completed`, `failed`, or `canceled`).
- Minimal audit entries are marked and protected from deletion operations.
- Storage threshold events must include `free_gb`, `threshold_gb`, and `action_taken` per storage safety contract.
- `job_id` is mandatory for job/stage/retry/publish events and may be null only for system-level storage monitor events when no active job exists.

## Retry Payload Shape

```json
{
  "operation_id": "publish:job_uuid:segment_uuid:youtube",
  "transient_error_code": "HTTP_429",
  "retry_after_seconds": 17,
  "strategy": "retry_after_or_exponential_backoff_with_jitter",
  "elapsed_seconds_since_first_failure": 142
}
```

## Cleanup Payload Shape

```json
{
  "actor_role": "operator",
  "target_class": "deletable_artifact|protected_minimal_audit",
  "target_id": "artifact-or-record-id",
  "outcome": "performed|rejected",
  "reason": "policy_protected|user_requested"
}
```

## Consumer Expectations

- UI progress view consumes stage and state events for transparent operator feedback.
- Recovery controller consumes checkpoint and retry events for deterministic resume behavior.
- Storage monitor/UX consumes threshold events to enforce warning/block/pause actions.
