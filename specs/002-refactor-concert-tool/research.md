# Phase 0 Research: CVCutter End-to-End Refactor

## Research Scope

- Technical Context unresolved items (`NEEDS CLARIFICATION`): none.
- Dependency-focused research: Flet UI migration, stream-first media processing, checkpoint persistence, retry/dedup safety, accessibility/localization, packaging/runtime.
- Integration-focused research: YouTube API, Google Forms API, configured AI provider API.

## Decisions

### 1) Decision: Flet-based MVVM presentation layer with externalized Japanese-first UI resources

- **Rationale**: FR-030 requires migration from `customtkinter` to Flet, and FR-043/FR-044 require Japanese coverage, keyboard-only operation, and accessibility controls. MVVM boundaries keep UI swappable and align with constitution layered design.
- **Alternatives considered**:
  - Keep `customtkinter`: lowest migration effort but directly violates FR-030.
  - Split into web frontend + backend: viable technically, but out of scope for desktop-only delivery and increases complexity.

### 2) Decision: Persist workflow state in local SQLite and keep large media artifacts on filesystem

- **Rationale**: FR-004/FR-018/FR-040/FR-051 require durable checkpoints, dedup identities, and non-deletable minimal audit records. SQLite provides transactional integrity, uniqueness constraints, and cross-process visibility on workstation deployments.
- **Alternatives considered**:
  - JSON-only state files: simple, but weak for concurrent writers, uniqueness guarantees, and audit durability.
  - External DB server: stronger centralization but unnecessary for single-workstation scope and operationally heavier.

### 3) Decision: FFmpeg-first stream/chunk processing pipeline with optional acceleration and CPU fallback

- **Rationale**: FR-013 and constitution stream-first principle require avoiding full-file/frame retention and maintaining peak RSS <= 8 GB on validation workloads. FFmpeg process pipelines plus chunked decoding provide bounded memory behavior and deterministic CPU fallback (FR-023).
- **Alternatives considered**:
  - OpenCV full-frame workflows: easier for some algorithms but memory-risky on long recordings.
  - Fully custom native processing stack: potentially faster, but higher implementation and maintenance cost.

### 4) Decision: Retry controller with `Retry-After` priority, exponential backoff + jitter, and 15-minute escalation deadline

- **Rationale**: FR-017/FR-032 fix retry policy semantics and deadline behavior. A centralized retry controller enforces consistent idempotent retry behavior and traceable retry outcomes across publish/integration operations.
- **Alternatives considered**:
  - Fixed-interval retry: simpler but less robust under rate limits and burst errors.
  - Unlimited retries: improves eventual completion chance but violates explicit escalation requirement.

### 5) Decision: Cross-process single-active-job and draft edit lock enforced through persistence-backed lock records

- **Rationale**: FR-031/FR-048 require workstation-wide exclusivity and concurrent-edit blocking. Lock records in SQLite (with heartbeat/stale detection) allow deterministic recovery and stale lock transition behavior aligned with FR-035.
- **Alternatives considered**:
  - In-memory process lock only: fails cross-process guarantees.
  - OS-global mutex only: process-level safety is strong, but weak for audit/history and stale-state lifecycle modeling.

### 6) Decision: Approved-service adapter contracts with pinned API versions and compatibility preflight checks

- **Rationale**: FR-016/FR-045 and CR-005 require strict approved integration scope and version compatibility checks before operations. Adapter boundaries isolate provider-specific SDK changes and make policy enforcement testable.
- **Alternatives considered**:
  - Direct SDK calls in workflow services: faster initially but spreads policy logic and version checks across modules.
  - Generic plugin marketplace model: over-generalized and unnecessary for fixed approved providers.

### 7) Decision: Keep plaintext credential mode with explicit risk warning + acknowledgement gate

- **Rationale**: Clarification and FR-037 explicitly accept plaintext credential storage for usability, but require explicit user warning and acknowledgement before enabling. A dedicated consent record ensures auditable user intent and transparent risk handling.
- **Alternatives considered**:
  - OS credential vault: safer at rest but contradicts accepted simplification decision for this feature.
  - Environment-variable only credentials: operationally fragile for non-engineering users and weak for guided setup UX.

### 8) Decision: Enforce metadata schema versioning with required `schema_version` and previous-version compatibility mapping

- **Rationale**: FR-049 requires explicit versioned ingestion and compatibility for at least the previous version. Versioned validators plus migration mapping reduce ambiguity and keep imports deterministic.
- **Alternatives considered**:
  - Infer schema version from fields: brittle and difficult to reason about.
  - Accept only current version: simpler implementation but violates backward compatibility requirement.

### 9) Decision: Structured event contract for stage start/completion/failure and retry outcomes

- **Rationale**: FR-024 and CR-008 require structured observability across core stages. A canonical event schema with job/stage/attempt context supports troubleshooting, audit, and acceptance verification.
- **Alternatives considered**:
  - Free-form text logs: flexible but poor for deterministic filtering and test assertions.
  - External observability stack dependency: unnecessary for local desktop scope.

### 10) Decision: Mandatory TDD + manual-judgment protocol artifact for core quality evaluations

- **Rationale**: Constitution CR-003 requires Red-Green-Refactor evidence and human-judgment protocol capture before execution (approver identity, date, procedures, materials, acceptance criteria), then post-run outcomes.
- **Alternatives considered**:
  - Code-first implementation: faster short-term, but non-compliant and regression-prone.
  - Manual judgment without protocol artifact: violates constitutional governance requirements.

## Resolution Status

All Technical Context items are now resolved with no remaining `NEEDS CLARIFICATION` placeholders.
