# Contract: External Integration Adapters

## Scope

Defines integration boundaries, allowed providers, compatibility checks, and retry/idempotency guarantees.

## Approved Integrations

- YouTube Data API (publishing destination)
- Google Forms API (metadata intake)
- Configured AI provider API (classification assistance)

All non-approved integrations are blocked by policy before operation dispatch.

## Adapter Interface (Conceptual)

```text
interface IntegrationAdapter:
  name() -> str
  pinned_api_version() -> str
  check_compatibility() -> CompatibilityResult
  execute(request: AdapterRequest, idempotency_key: str) -> AdapterResult
```

## AdapterRequest (Normative)

```json
{
  "operation": "publish_segment | fetch_form_responses | classify_content",
  "job_id": "uuid",
  "segment_id": "uuid|null",
  "destination": "youtube|null",
  "payload": {},
  "timeout_seconds": 120,
  "requested_at": "2026-03-14T23:49:01Z"
}
```

Required fields for retry/idempotency orchestration:

- `operation`
- `job_id`
- `payload`
- `requested_at`

Conditional requirements:

- For `operation=publish_segment`, `segment_id` and `destination` are mandatory and non-null.
- For non-publish operations, `segment_id` and `destination` may be null.

## AdapterResult (Normative)

```json
{
  "provider": "youtube|google_forms|configured_ai",
  "operation": "publish_segment",
  "category": "success|transient|blocking|policy",
  "error_code": "HTTP_429|null",
  "retry_after_seconds": null,
  "terminal": false,
  "correlation_id": "provider-request-id",
  "idempotency_outcome": "performed|duplicate_suppressed|unknown",
  "external_object_id": "video_id|null",
  "message": "human actionable guidance",
  "recommended_next_action": "retry_later|check_credentials|fix_policy_configuration"
}
```

AdapterResult requirements:

- `category` and `terminal` are mandatory for control-flow decisions.
- `retry_after_seconds` type is `number|null`.
- `retry_after_seconds` is required when provider supplies `Retry-After`.
- When provider does not supply `Retry-After`, `retry_after_seconds` must be `null`.
- `idempotency_outcome` is mandatory for retry-safe duplicate control.
- `correlation_id` is mandatory when provider exposes request correlation.
- `recommended_next_action` is mandatory for error-category results.

## Compatibility Contract

- Each adapter declares pinned supported API version(s).
- Preflight compatibility check runs before processing/publishing operations.
- Incompatibility blocks execution and returns remediation guidance.

## Idempotency Contract

- Publish operations use dedup key: (`job_id`, `segment_id`, `destination`).
- Retry operations must not produce duplicate side effects when the previous attempt partially succeeded.
- Adapter responses must include stable correlation identifiers where available.

## Retry Contract

- Retry policy:
  - Prioritize `Retry-After` when provided.
  - Otherwise exponential backoff with jitter (initial 1s, max 60s).
  - Escalate to manual intervention after 15 minutes from first transient failure for each operation.
- Retry outcomes are emitted to structured event ledger.

## Credential Contract

- Plaintext local credential mode is allowed for this feature.
- Enabling plaintext mode requires explicit user acknowledgement after security warning display.
- Credential source and consent state must be auditable.

## Error Contract

- Errors must include:
  - `category` (`transient`/`blocking`/`policy`)
  - `provider`
  - `operation`
  - `error_code`
  - `terminal`
  - `correlation_id` (when available)
  - `recommended_next_action`
- Policy violations (for example non-approved destination) are non-retryable.
