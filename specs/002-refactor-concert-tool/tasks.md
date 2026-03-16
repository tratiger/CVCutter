# Tasks: CVCutter End-to-End Refactor

## Inputs

- `spec.md`
- `plan.md`
- `research.md`
- `data-model.md`
- `quickstart.md`
- `contracts/*.md`

## Delivery Rule

All implementation follows Red-Green-Refactor and must pass:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest --cov`

Task IDs are stable identifiers; execution order follows the list order in this file. Tasks marked `[P]` may run in parallel only after prerequisite RED tasks for the same behavior have completed.

## Phase 1: Architecture and Persistence Foundation

- [ ] T003 (RED) Add domain unit tests for `ProcessingJob` lifecycle transitions including stale recovery path.
- [ ] T093 (RED) Add tests proving core business logic (domain/application) executes without GUI-layer imports/runtime (CR-010).
- [ ] T005 (RED) Add tests for uniqueness constraints: checkpoint key and publish dedup key.
- [ ] T001 Create layered package structure under `src/cvcutter/{presentation,application,domain,infrastructure,shared}`.
- [ ] T002 Add dependency wiring and app bootstrap for Flet-based presentation entrypoint.
- [ ] T094 [P] Implement test isolation boundaries and a GUI-free core-test execution target for CR-010 validation.
- [ ] T008 [P] Add SQLite schema migration for all persisted entities: jobs, checkpoints, segment candidates, audio profiles, mapping records, publish tasks, event ledger, config-change records, role-policy records, locks, and cleanup logs.
- [ ] T004 Implement lifecycle transition guards and invalid-transition errors.
- [ ] T006 Implement persistence-level uniqueness and dedup enforcement.
- [ ] T084 (RED) Add processing-event contract tests covering required event taxonomy, stage start/completion/failure semantics, retry payload requirements, terminal outcomes, `job_id` nullability rules, and storage-event required payload fields (`free_gb`, `threshold_gb`, `action_taken`).
- [ ] T087 (RED) Add append-only event-store integrity tests (no historical mutation/deletion in normal flows).
- [ ] T007 Add structured event writer with schema version support.
- [ ] T088 Implement append-only event transport enforcement for event ledger writes.

## Phase 2: Governance and Protocol Setup (Before Manual Validation)

- [ ] T009 Validate/update the existing `plan.md` `Manual Test Protocol` section so all required fields are concrete and reviewer-visible.
- [ ] T010 Add an execution guard that blocks manual-judgment test tasks unless protocol fields are present **and** approver identity is validated as requesting user/designated domain reviewer (explicitly rejecting implementer self-approval).
- [ ] T011 Add a post-execution checklist step that requires updating the same protocol section with observed results and approver pass/fail date.

## Phase 3: Resume, Retry, and Safety Core (P1)

- [ ] T012 (RED) Add interrupted-run resume integration test for first-incomplete-stage restart.
- [ ] T013 Implement checkpoint orchestrator and resume cursor handling.
- [ ] T014 (RED) Add retry-policy tests (`Retry-After`, backoff+jitter, 15-minute escalation).
- [ ] T015 Implement centralized retry controller with idempotent operation envelopes.
- [ ] T016 (RED) Add tests for single-active-job and cross-process startup stale-state handling.
- [ ] T017 [P] Implement workstation-wide active-job lock and stale transition `running -> paused -> resumable`.
- [ ] T018 (RED) Add storage-threshold tests for `<20 GB`, `<10 GB`, `<5 GB` behaviors including explicit operator-confirmed retry gate before resume/unblock.
- [ ] T019 [P] Implement storage monitor and threshold action policy with event emission and operator confirmation gate for unblock.
- [ ] T020 (RED) Add tests for config-change detection and dependency-map-based invalidate-or-cancel gating before resume (FR-021).
- [ ] T021 Implement config-change detector and checkpoint invalidation decision workflow.

## Phase 4: Classification and Metadata Mapping Rules (P2/P3)

- [ ] T022 (RED) Add unit tests for confidence decision rules (`>=70`, `+10 margin`, single-candidate rule) (FR-029).
- [ ] T082 (RED) Add tests for per-job classification strategy persistence across save/restart/resume (FR-019).
- [ ] T023 [P] Implement classification decision engine and `no_confident_match` output.
- [ ] T083 [P] Implement per-job strategy persistence and resume-time strategy restoration.
- [ ] T024 (RED) Add tests for timestamp-strategy validity checks (ISO-8601 parse, event-window derivation, +/-10m tolerance) (FR-034).
- [ ] T025 [P] Implement timestamp metadata validator and block-with-guidance behavior.
- [ ] T026 (RED) Add tests for strategy-switch guidance when no confident match exists (FR-026).
- [ ] T027 Implement operator guidance flow for strategy switch and matching-input adjustment.
- [ ] T028 (RED) Add tests for per-job low-confidence threshold config (0-100, default 70) including persistence (FR-022).
- [ ] T029 Implement threshold config UI/model persistence and enforcement.
- [ ] T030 (RED) Add contract tests for metadata validation rules: schema versions, mixed-version CSV rejection, required-field constraints, enum/length checks, JSON top-level/per-record mismatch, and unknown-field warning behavior.
- [ ] T031 Implement metadata import normalization, alias mapping, compatibility transformation, and full contract validator/error-warn semantics.
- [ ] T032 (RED) Add tests for segment-to-metadata mapping before publish (FR-014).
- [ ] T033 Implement validated metadata mapping enforcement for every finalized segment.
- [ ] T034 (RED) Add tests for model availability preflight and reduced-confidence fallback/blocking behavior (FR-028).
- [ ] T035 Implement model-availability checker and modality fallback/block decision logic.
- [ ] T077 (RED) Add tests for pre-performance speech transcription matching with confidence and traceable source context output (FR-019).
- [ ] T078 Implement transcription ingestion, program/song-list matching, and source-context trace emission.

## Phase 5: Segmentation, Sync, and Media Pipeline (P3)

- [ ] T036 (RED) Add tests for stream-first processing guarantees and memory-bound checks.
- [ ] T037 [P] Implement FFmpeg-first chunk/stream pipeline with CPU fallback.
- [ ] T038 (RED) Add tests for multimodal disagreement candidate generation and low-confidence review flags.
- [ ] T039 [P] Implement confidence-weighted boundary candidate aggregation.
- [ ] T040 (RED) Add tests for single-source sync edge cases (auto-skip embedded-only, manual required external-only).
- [ ] T041 [P] Implement sync-stage branching and manual-sync gating.
- [ ] T042 (RED) Add tests for median alignment error evaluation (80 ms threshold).
- [ ] T043 Implement synchronization quality evaluator and manual-correction flags.
- [ ] T085 (RED) Add tests for switchable audio tuning modes (simple sliders vs waveform/manual offset) and tuning-state persistence (FR-012).
- [ ] T086 Implement tuning-mode switching UI/domain flow and waveform/manual-offset controls for pre-export adjustment.
- [ ] T089 (RED) Add tests that block export/publish while low-confidence segments requiring review remain unconfirmed.
- [ ] T090 Implement export/publish confirmation gate for `requires_review` segment candidates.
- [ ] T091 (RED) Add tests that block publish when sync outputs are flagged for manual correction until correction is completed.
- [ ] T092 Implement publish precondition enforcing sync correction completion before publish.

## Phase 6: Publishing and External Integrations (P4)

- [ ] T044 (RED) Add adapter contract tests for `AdapterRequest`/`AdapterResult` semantics.
- [ ] T097 (RED) Add tests for pinned API-version inventory checks and incompatibility block/remediation behavior (FR-045).
- [ ] T045 [P] Implement approved-provider adapters (YouTube, Google Forms, configured AI) with pinned-version inventory and compatibility preflight checks.
- [ ] T046 (RED) Add tests for publish dedup suppression and retry outcomes.
- [ ] T047 [P] Implement publish task executor with idempotency keys and retry telemetry.
- [ ] T048 (RED) Add tests for policy rejection of non-approved destinations.
- [ ] T049 [P] Implement destination policy gate and operator remediation messaging.
- [ ] T050 (RED) Add tests for plaintext credential warning+consent gate behavior.
- [ ] T051 Implement credential consent flow and auditable consent record handling.
- [ ] T052 (RED) Add export tests for optional opening-title overlay toggle and duration control (FR-015).
- [ ] T053 Implement opening-title insertion pipeline and operator-configurable duration.
- [ ] T054 (RED) Add format matrix tests for ingest/export support (`MP4`/`MOV`/`MKV`/`MTS`, `WAV`/`FLAC`/`AAC`, `CSV`/`JSON`, output `MP4`+`AAC`) (FR-039).
- [ ] T055 Implement strict format validation and conversion constraints for supported matrix.

## Phase 7: UI, Accessibility, Role Model, and Lock UX (P2/P5)

- [ ] T056 (RED) Add UI workflow tests for setup/progress/review/publish coverage traceability.
- [ ] T057 [P] Implement Flet wizard setup, progress dashboard, and recovery guidance screens.
- [ ] T058 (RED) Add accessibility tests for keyboard-only workflows and focus visibility.
- [ ] T059 [P] Implement keyboard navigation, focus indicators, and contrast-compliant theme behavior.
- [ ] T060 (RED) Add localization tests for complete Japanese UI string coverage.
- [ ] T061 Implement externalized string resources and localization loader.
- [ ] T062 (RED) Add tests for executable role normalization (`operator` only) and non-operator rejection (FR-050).
- [ ] T063 Implement authorization enforcement that prevents `editor`/`publisher` role-branch execution paths.
- [ ] T064 (RED) Add tests for exclusive draft edit lock behavior across app instances.
- [ ] T065 Implement draft edit lock UX and conflict guidance.

## Phase 8: Cleanup, Audit, and Packaging (P4/P5)

- [ ] T066 (RED) Add tests verifying non-deletable minimal audit ledger protection.
- [ ] T067 [P] Implement cleanup manager for deletable artifacts and rejection path for protected records.
- [ ] T068 (RED) Add tests for cleanup event emission (`cleanup.performed`, `cleanup.rejected`) including required payload fields (`actor_role`, `target_class`, `target_id`, `outcome`, `reason`).
- [ ] T069 [P] Implement cleanup event payload integration with event stream.
- [ ] T070 (RED) Add installer validation tests for supported and unsupported environments.
- [ ] T071 Implement packaging pipeline and first-launch onboarding checks for non-engineering users.

## Phase 9: End-to-End Verification and Hardening (Final Gate)

- [ ] T072 Run scenario validations from `quickstart.md` (including FR-021, FR-038, FR-022, FR-028 paths).
- [ ] T073 Update `Manual Test Protocol` artifact with post-execution observed results and approver pass/fail date.
- [ ] T099 (RED) Add compliance-scope regression test asserting no new external regulatory workflow gates are introduced (FR-046).
- [ ] T100 Implement compliance-scope verification artifact generation and fail delivery when FR-046 scope is violated.
- [ ] T074 Execute full quality gates (`uv run ruff check .`, `uv run pyright`, `uv run pytest --cov`) and resolve failures.
- [ ] T095 Execute GUI-independent core-test gate and record proof that business-logic tests pass without GUI dependencies.
- [ ] T075 Produce workflow traceability matrix (FR-001..FR-051 -> implementation/tests).
- [ ] T096 Verify `plan.md` contains updated CR-007 rejected-abstraction notes and CR-009 tradeoff decision log entries for all material design conflicts.
- [ ] T079 Define SC-001..SC-010 measurement protocol and data-capture templates.
- [ ] T080 Execute metric collection runs/participant evaluations required by SC-001..SC-010 sample sizes.
- [ ] T081 Produce success-criteria report with measured values and pass/fail decisions for SC-001..SC-010.
- [ ] T076 Run final multi-perspective code review and resolve all material findings.
