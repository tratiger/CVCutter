<!--
Sync Impact Report
- Version change: 1.0.0 -> 1.1.0
- Modified principles:
  - III. Test-First Reliability (NON-NEGOTIABLE) -> III. Test-First Reliability (NON-NEGOTIABLE)
- Modified sections:
  - Delivery Workflow & Quality Gates
- Removed sections:
  - None
- Templates requiring updates:
  - pending: .specify/templates/plan-template.md (not updated in this commit; follow-up required)
  - pending: .specify/templates/spec-template.md (not updated in this commit; follow-up required)
  - pending: .specify/templates/tasks-template.md (not updated in this commit; follow-up required)
  - pending: .specify/templates/commands/*.md (directory not present in this repository)
- Runtime guidance review:
  - [REVIEWED] README.md (no direct constitution references to update)
  - [REVIEWED] AGENTS.md (reviewed for principle consistency in this update)
  - [REVIEWED] docs/developer_manual.md and docs/user_manual.md (no direct constitution references)
- Follow-up items:
  - Create or restore `.specify/templates/commands/` if command-specific templates are required.
  - Apply the v1.1.0 user-in-the-loop testing requirement to plan/spec/tasks templates.
-->

# CVCutter Constitution

## Core Principles

### I. Domain-Centric Layered Design
The codebase MUST separate UI, application orchestration, domain logic, and infrastructure adapters.
Core video splitting, audio sync, mapping, upload rules, and workflow state/retry rules MUST remain
executable and testable without GUI dependencies. For constitutional compliance, "core modules" are modules
implementing performance detection/splitting, audio synchronization/mixing, metadata mapping, upload
orchestration, or split/sync/map/upload checkpoint-retry-idempotency business rules, regardless of package
path. Module boundaries MUST follow clear bounded contexts to keep refactoring safe.
Rationale: layered boundaries reduce coupling and allow UI framework changes without destabilizing core
behavior.

### II. Stream-First Media Processing
Long media handling MUST use chunked or streaming pipelines when feasible and MUST avoid full-file,
full-frame memory retention for production workflows. Implementations MUST define explicit memory-aware
processing steps and graceful CPU fallback when optional GPU acceleration is unavailable.
Rationale: concert recordings are large; stream-first pipelines prevent memory exhaustion and improve
operational reliability.

### III. Test-First Reliability (NON-NEGOTIABLE)
Every behavior change MUST follow Red-Green-Refactor: write tests first, verify failure, implement, then
refactor. Every bug fix MUST include at least one regression test that fails before the fix and passes
afterward. Business logic tests MUST run independently of GUI layers. For core-module validations that rely
on human judgment (for example, whether performance segmentation output is correct), teams MUST ask the
requesting user or a designated domain reviewer (not the implementer) for detailed test procedures,
required test materials, and acceptance criteria before executing those tests.
Rationale: enforced TDD protects critical media workflows and prevents recurring production regressions.

### IV. Deterministic Automation & Resume Safety
Multi-step workflows (split, sync, map, upload) MUST persist resumable state and support restart from the
last successful checkpoint. Retry paths MUST be explicit and idempotent, and failures MUST surface
actionable diagnostics instead of silent fallbacks.
Rationale: long-running pipelines and external APIs are failure-prone; deterministic resumes minimize
operator intervention and duplicated work.

### V. Approved Integrations, Observability, and Simplicity
External integrations MUST be limited to approved providers for this project scope (YouTube API, Google
Forms API, and configured AI API). Core processing steps MUST emit structured logs for start, completion,
and failure paths. Design choices MUST favor the simplest solution that satisfies current requirements and
MUST avoid speculative abstractions.
Rationale: constrained integrations reduce compliance risk, and observability plus simplicity improve
supportability and maintenance speed.

## Engineering Constraints & Standards

- Runtime and tooling MUST target Python 3.11+ and use `uv` for dependency management and command
  execution.
- Quality verification for delivery candidates MUST include:
  - `uv run ruff check .`
  - `uv run pyright`
  - `uv run pytest --cov`
- Code introducing hard-coded secrets, credentials, or token material is prohibited.
- New modules approaching 1000 lines MUST be split into coherent subpackages before merge.
- UI-layer evolution SHOULD keep framework adapters replaceable to support planned modernization without
  reworking domain logic.

## Delivery Workflow & Quality Gates

All substantial changes MUST follow this sequence:

1. Investigate current behavior and create an execution plan.
2. Define or update failing tests first (Red), including tests that require manual human judgment.
3. For manual human-judgment tests in core modules, ask the requesting user or designated domain reviewer
   (not the implementer) for detailed procedures, required test materials, and acceptance criteria before
   test execution.
4. Record the pre-execution manual test protocol in a traceable artifact (plan entry, task item, or PR
   checklist) with reviewer-visible reference. At minimum, the artifact MUST include approver identity, date,
   procedures, test materials, and acceptance criteria. If no template field exists yet, record it in the PR
   description section titled `Manual Test Protocol`.
5. Implement minimal changes to satisfy tests.
6. Re-run tests and quality checks until Green, including required manual human-judgment tests and recorded
   approver pass/fail outcomes.
7. Update the same manual test artifact with observed results and approver pass/fail determination date after
   test execution.
8. Refactor for KISS, DRY, and clear object boundaries.
9. Run multi-perspective code review and resolve all material findings before closure.

A change is compliant only when requirements, tests, linting, static analysis, and constitutional gates all
pass together in the same change set.

## Governance

This constitution is the primary engineering authority for CVCutter. In case of conflict, this document
supersedes routine project conventions and templates.

Amendment process:

1. Propose constitutional changes in a dedicated change set with explicit rationale.
2. Update dependent templates and runtime guidance in the same change set or record explicit pending items.
3. Prepend a Sync Impact Report to `.specify/memory/constitution.md` documenting scope and propagation.
4. Obtain maintainer approval before adoption.

Versioning policy:

- MAJOR: backward-incompatible principle removal or redefinition.
- MINOR: new principle/section or materially expanded governance guidance.
- PATCH: wording clarifications, typos, or non-semantic refinements.

Compliance review expectations:

- Every plan MUST pass a Constitution Check before implementation begins.
- Every implementation review MUST verify TDD evidence and required quality gate command results.
- Every implementation review MUST verify evidence that user-defined manual test procedures, required test
  materials, and acceptance criteria were collected before running human-judgment core-module tests, and
  that the approver is the requesting user or designated domain reviewer (not the implementer). The evidence
  artifact MUST include a date and reviewer-visible reference.
- Every implementation review MUST verify the same artifact was updated after execution with observed
  results and approver pass/fail determination date.
- Non-compliant changes MUST not be merged without a documented exception and migration plan.

**Version**: 1.1.0 | **Ratified**: 2026-03-11 | **Last Amended**: 2026-03-12
