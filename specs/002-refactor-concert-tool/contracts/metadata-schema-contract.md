# Contract: Metadata Import Schema

## Scope

Defines the external metadata payload contract consumed by CVCutter for mapping segment outputs to publish metadata.

## Supported Formats

- `CSV` (UTF-8, comma delimiter, RFC 4180 quoting)
- `JSON` (UTF-8)

## Canonical Record Model

Each input record normalizes to this canonical model:

```json
{
  "program_id": "P-001",
  "segment_title": "Example Performance",
  "performer_display_name": "Performer Name",
  "publish_visibility": "public",
  "description": "Optional",
  "tags": ["concert", "example"],
  "playlist_id": "PLxxxx(optional)",
  "operator_note": "optional"
}
```

`schema_version` is payload metadata and is intentionally excluded from the canonical per-record model.

## Normative Field Table

| Field | Type | Required | Constraints | CSV Representation |
|---|---|---|---|---|
| `payload.schema_version` | string | Yes | Numeric string (`"1"`, `"2"`, ...). Missing/empty rejected. Authoritative at JSON top-level and CSV row-level. | `schema_version` column (per CSV row) |
| `program_id` | string | Yes | 1..128 chars after trim. Canonical identifier for mapping. | `program_id` column |
| `segment_title` | string | Yes | 1..200 chars after trim. | `segment_title` column |
| `performer_display_name` | string | Yes | 1..200 chars after trim. | `performer_display_name` column |
| `publish_visibility` | string | Yes | Enum: `public` \| `unlisted` \| `private` | `publish_visibility` column |
| `description` | string | No | <= 5000 chars | `description` column |
| `tags` | array[string] | No | Each tag <= 100 chars, max 30 tags | Semicolon-delimited in single `tags` column |
| `playlist_id` | string | No | <= 128 chars | `playlist_id` column |
| `operator_note` | string | No | <= 1000 chars | `operator_note` column |

## Accepted Input Alias Mapping

```json
{
  "accepted_aliases": {
    "event_id": "program_id",
    "title": "segment_title",
    "performer": "performer_display_name",
    "visibility": "publish_visibility"
  }
}
```

Alias mapping is only applied for explicitly accepted previous-version compatibility inputs.

## JSON Payload Shape

```text
{
  "schema_version": "2",
  "records": [canonical_record, ...]
}
```

## CSV Canonical Columns (Header Order)

```text
schema_version,program_id,segment_title,performer_display_name,publish_visibility,description,tags,playlist_id,operator_note
```

## Version Baseline (Normative)

- `CURRENT_SCHEMA_VERSION = "2"`
- `PREVIOUS_SCHEMA_VERSION = "1"`

## Compatibility Rules

- Import without `schema_version` is rejected.
- Accepted versions are exactly `CURRENT_SCHEMA_VERSION` and `PREVIOUS_SCHEMA_VERSION`.
- Previous-version payloads are transformed via explicit compatibility mapping before validation.
- Unknown future versions are rejected with remediation guidance.
- Unknown fields are ignored only after warning; malformed required fields fail validation.
- For JSON payloads, top-level `schema_version` is authoritative.
- Legacy JSON payloads may include per-record `schema_version`; when present, every record value must match top-level or import is rejected.
- CSV payloads containing mixed `schema_version` values across rows are rejected as a single invalid import batch.

## Validation Semantics

- Contract validation runs before execution start (and before publish stage when re-imported).
- Invalid payloads produce actionable error guidance.
- Successful validation emits a structured metadata-validation success event.
