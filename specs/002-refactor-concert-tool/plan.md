# Implementation Plan: CVCutter End-to-End Refactor

**Branch**: `002-refactor-concert-tool` | **Date**: 2026-03-14 | **Spec**: `C:\Users\trati\development\CVCutter\specs\002-refactor-concert-tool\spec.md`
**Input**: Feature specification from `C:\Users\trati\development\CVCutter\specs\002-refactor-concert-tool\spec.md`

## Summary

Refactor CVCutter into a constitution-compliant layered desktop system that delivers resume-safe concert processing (split/sync/map/publish), migrates the UI to Flet, preserves deterministic retry and dedup behavior, and improves installability and operator guidance on Windows/macOS.  
The implementation uses explicit bounded contexts (presentation, application, domain, infrastructure), stream-first media processing, checkpoint-driven orchestration, and policy-constrained external adapters (YouTube, Google Forms, configured AI provider).

## Technical Context

**Language/Version**: Python 3.11+ (project baseline remains `>=3.11`)  
**Primary Dependencies**: Flet (UI migration target), moviepy/opencv-python/librosa/pydub/scipy/ffmpeg toolchain, google-api-python-client stack, configured AI provider adapter (default: Gemini), `uv`-managed packaging/runtime  
**Storage**: Local filesystem for media/artifacts + local SQLite for checkpoints, lock state, retry/audit ledger, and dedup keys  
**Testing**: `pytest`, `pytest-cov`, `ruff`, `pyright`; layered unit/integration/contract coverage with Red-Green-Refactor evidence  
**Target Platform**: Windows 10/11 (64-bit) and macOS 13+ (Apple Silicon/Intel) desktop  
**Project Type**: Python desktop application (Flet presentation + layered backend pipeline)  
**Performance Goals**: Peak RSS <= 8 GB for validation-profile sync workloads (long recordings, up to 4 audio sources); transient publish failure recovery window <= 15 minutes per output item; no duplicate side effects on resume/retry  
**Constraints**: Single active job per workstation (cross-process), single executable role (`operator`) with context-only labels (`editor`/`publisher`), approved integrations only, plaintext credential mode requires explicit risk acknowledgment, no auto-deletion of non-audit artifacts, packaged install must not require developer setup, Japanese-first UI with keyboard/WCAG 2.1 AA-equivalent support  
**Scale/Scope**: Single-workstation operation with long-form concert inputs; validation dataset includes 20 long runs, >=200 segment candidates, >=200 classification attempts; cloud-distributed execution and mobile UI are out of scope

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Gate Assessment

- [x] **Layered Boundaries**: Architecture is planned as `presentation` (Flet UI), `application` (use-case orchestration), `domain` (entities/rules/state), and `infrastructure` (FFmpeg/media IO/API adapters/persistence).
- [x] **Stream-First Processing**: Long-media stages are planned with chunk/stream processing and explicit memory-bounded operation (FR-013 / SC-002).
- [x] **Test-First Delivery**: Delivery plan enforces Red-Green-Refactor and requires failing tests before implementation, including regression tests for each defect.
- [x] **Resume & Retry Safety**: Stage checkpoints, idempotent dedup keys, and retry envelopes (Retry-After + backoff + jitter + 15-minute escalation) are included in core design.
- [x] **Approved Integrations**: Integrations are restricted to YouTube API, Google Forms API, and configured AI provider adapter; non-approved destinations are blocked.
- [x] **Quality Gates**: Validation requires `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov`.
- [x] **GUI-Independent Core Tests (CR-010)**: Core business-logic tests are planned to run independently from GUI-layer dependencies.

### Post-Design Re-check

- [x] **Layered Boundaries**: `data-model.md` enforces separation of workflow/domain/infrastructure concerns, and contracts isolate external adapter boundaries.
- [x] **Stream-First Processing**: `research.md` Decision 3 and `data-model.md` processing entities specify memory-bounded stream/chunk behavior and CPU fallback.
- [x] **Test-First Delivery**: `quickstart.md` defines quality gate commands and manual-judgment protocol requirements aligned with constitutional Red-Green-Refactor workflow.
- [x] **Resume & Retry Safety**: `data-model.md` checkpoint/dedup entities plus `contracts/processing-events-contract.md` and `contracts/external-integration-contract.md` define resumable and idempotent retry semantics.
- [x] **Approved Integrations**: `contracts/external-integration-contract.md` limits integrations to approved providers and blocks non-approved destinations.
- [x] **Contract Coverage**: `contracts/*.md` (metadata-schema, processing-events, external-integration, authorization-role, storage-safety, classification-decision, packaging-install, cleanup-retention) are reflected in the design/task scope.
- [x] **Quality Gates**: `quickstart.md` explicitly captures `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov`.
- [x] **GUI-Independent Core Tests (CR-010)**: `tasks.md` includes GUI-independent core-test gate tasks and `quickstart.md` includes explicit validation for GUI-free business-logic test execution.

## Manual Test Protocol (Pre-Execution Record)

> This section must be approved before running manual-judgment core-module tests.

- **Approver**: `trati` (requesting user / operator-side domain reviewer; not implementer)
- **Approval Date**: 2026-03-14
- **Procedures**:
  1. Run the 20-run validation set with checkpoint/retry enabled.
  2. Collect segmentation candidates and synchronization metrics for manual-judgment subset.
  3. Review low-confidence boundaries and flagged sync outputs with the approver.
  4. Record accept/reject decisions and correction notes per sampled item.
- **Required Test Materials**:
  - Validation datasets defined in `spec.md` (`Synchronization/Segmentation Validation Set`, `Classification Validation Set`)
  - Ground-truth boundary annotations and reference audio alignment offsets
  - Build identifier and configuration profile used for the run
- **Acceptance Criteria**:
  - Segment acceptance rate meets SC-003 threshold
  - Sync quality meets SC-008 threshold or flagged outputs have manual-correction rationale
  - Resume/retry traceability is present for reviewed runs
- **Post-Execution Results (2026-03-18)**:
  - Automated evidence run completed:
    - `uv run ruff check .` / `uv run pyright` / `uv run pytest --cov -q` all passed.
    - Packaging build `uv run python build_exe.py` succeeded and `dist/CVCutter.exe` was generated.
  - Manual-judgment protocol status:
    - Human-reviewed segmentation/synchronization/classification dataset runs are **not yet executed**.
    - Final manual pass/fail date remains pending approver execution.

### Segmentation Manual Test Addendum (2026-03-17)

- **Scope**: `src/cvcutter/infrastructure/media/segmentation_pipeline.py` (OpenCV MOG2-based implementation)  
- **Related RED/GREEN Test**: `tests/unit/domain/segmentation/test_multimodal_disagreement_candidates.py`
- **Manual Procedures (Segmentation-Focused)**:
  1. Launch the app and create a draft from onboarding.
  2. Run the segmentation stage on:
     - synthetic transition sample (black/white frame-switch style),
     - real validation clips from the segmentation validation set.
  3. Capture proposed segment boundaries and confidence labels.
  4. Compare boundaries against ground-truth annotations and record deviation.
  5. For low-confidence candidates, perform operator confirmation flow and record accept/adjust/reject outcomes.
- **Segmentation Acceptance Criteria**:
  - Synthetic sample reproduces expected split count and boundary windows (two candidate regions for the prepared dummy transition stream).
  - Real validation clips satisfy SC-003 threshold after required low-confidence confirmations.
  - No duplicate candidate emission on re-run with identical inputs and settings.
  - Peak RSS remains within FR-013 bound (`<= 8 GB`) during validation-profile segmentation runs.
- **Execution Record Template**:
  - Run date:
  - Dataset IDs:
  - Segment acceptance rate:
  - Low-confidence reviewed count:
  - Notable corrections:
  - Pass/Fail decision:

## Project Structure

### Documentation (this feature)

```text
specs/002-refactor-concert-tool/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── *.md              # Validation evidence artifacts
├── contracts/
│   ├── metadata-schema-contract.md
│   ├── processing-events-contract.md
│   ├── external-integration-contract.md
│   ├── authorization-role-contract.md
│   ├── storage-safety-contract.md
│   ├── classification-decision-contract.md
│   ├── packaging-install-contract.md
│   └── cleanup-retention-contract.md
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
build_exe.py
src/cvcutter/
├── app.py
├── presentation/
│   ├── flet_app/
│   │   ├── views/
│   │   ├── viewmodels/
│   │   └── localization/
│   └── controllers/
├── application/
│   ├── workflows/
│   ├── services/
│   └── dto/
├── domain/
│   ├── jobs/
│   ├── checkpoints/
│   ├── segmentation/
│   ├── synchronization/
│   ├── classification/
│   ├── publishing/
│   └── policies/
├── infrastructure/
│   ├── persistence/
│   ├── media/
│   ├── integrations/
│   ├── packaging/
│   └── observability/
└── shared/
    ├── config/
    └── types/

tests/
├── unit/
├── integration/
└── contract/
```

**Structure Decision**: Keep the current single-project Python package and refactor into constitution-aligned layered subpackages under `src/cvcutter`. This minimizes operational risk while removing monolithic module coupling and enables TDD at domain/application boundaries.

## Simplicity Decisions (CR-007)

Rejected speculative abstractions:

- **Rejected**: Multi-repository split (core pipeline vs UI vs integrations).  
  **Reason**: adds operational complexity before core reliability goals are met.
- **Rejected**: Generic third-party integration plugin framework.  
  **Reason**: current scope has fixed approved providers; plugin system is premature.
- **Rejected**: Remote service orchestration for processing stages.  
  **Reason**: feature scope is single-workstation desktop execution only.
- **Rejected**: Always-on external observability stack dependency.  
  **Reason**: structured local event ledger satisfies current diagnostic requirements.

## Tradeoff Decision Log (CR-009)

| Decision Topic | Alternatives Considered | Priority Application (CR-009) | Chosen Outcome |
|---|---|---|---|
| Credential storage mode | OS vault vs plaintext local config | `data integrity/dedup` remains preserved (checkpoint/dedup keys and audit ledger behavior unchanged); within that constraint, `recoverability/usability` prioritized after explicit risk acceptance | Plaintext mode with mandatory warning + explicit consent |
| Retry behavior under API instability | aggressive indefinite retry vs bounded retry window | `data integrity/dedup` and `recoverability` prioritized over throughput | Idempotent retry with 15-minute escalation window |
| Storage exhaustion recovery | auto-resume vs explicit confirmation | `data integrity` and `recoverability` prioritized over convenience | Explicit operator confirmation required before resume/unblock |
| Audit retention vs manual cleanup scope (FR-018 vs FR-038) | fully deletable history vs protected minimal audit + selective cleanup | `data integrity/dedup` and `recoverability` preserved by making minimal audit ledger non-deletable while allowing operator cleanup of non-audit artifacts | Constrained cleanup policy: protected minimal audit records + user-managed deletion for non-audit artifacts |

## Complexity Tracking

No constitutional violations identified at planning stage; no exceptions required.
