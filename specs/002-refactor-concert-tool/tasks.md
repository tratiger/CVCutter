# Tasks: CVCutter End-to-End Refactor

**Input**: Design documents from `specs/002-refactor-concert-tool/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Test tasks are required for this feature because `spec.md` mandates TDD evidence (CR-003) and quality-gate validation.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `- [X] T### [P?] [US?] Description with file path`

- `[P]` means the task can run in parallel (different files, no dependency on incomplete tasks).
- `[US#]` labels appear only in user story phases.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize project structure, tooling, and baseline app shell for refactor work.

- [X] T001 Create layered package directories in `src/cvcutter/{presentation,application,domain,infrastructure,shared}`.
- [X] T002 Configure application entry points and `uv` scripts in `pyproject.toml`.
- [X] T003 Configure lint/type/test tooling defaults in `pyproject.toml`.
- [X] T004 [P] Create shared test fixtures for SQLite/media stubs in `tests/conftest.py`.
- [X] T005 [P] Add workflow stage constants and enums in `src/cvcutter/domain/jobs/stages.py`.
- [X] T006 Create Flet shell bootstrap wiring in `src/cvcutter/app.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core persistence, eventing, and safety primitives that block all user stories.

**⚠️ CRITICAL**: No user story implementation starts before this phase is complete.

- [X] T007 [P] Add lifecycle transition RED tests for `ProcessingJob` in `tests/unit/domain/jobs/test_processing_job_lifecycle.py`.
- [X] T008 [P] Add foundational uniqueness and lock-acquisition RED tests for checkpoint/publish keys and active-job/draft locks in `tests/integration/persistence/test_uniqueness_constraints.py`.
- [X] T009 [P] Add processing-event RED contract tests for `job.created`/`job.state_changed`, envelope, retry payloads, terminal outcomes, and `job_id` nullability in `tests/contract/test_processing_event_contract.py`.
- [X] T010 Implement `ProcessingJob` aggregate transitions with executable-role guard hooks in `src/cvcutter/domain/jobs/processing_job.py`.
- [X] T011 Implement SQLite base schema for jobs/checkpoints/config-change-records/segments/audio/mapping/publishing/events/locks/role-policy in `src/cvcutter/infrastructure/persistence/migrations/001_initial_schema.sql`.
- [X] T012 Implement persistence repositories for core aggregates including `OperatorRolePolicy` and `ConfigurationChangeRecord` in `src/cvcutter/infrastructure/persistence/repositories.py`.
- [X] T013 Implement append-only event ledger writer with mutation/deletion guards in `src/cvcutter/infrastructure/observability/event_ledger.py`.
- [X] T014 Implement workstation active-job + draft-lock management in `src/cvcutter/application/services/lock_service.py`.
- [X] T015 Implement configuration-change dependency map policy in `src/cvcutter/domain/checkpoints/config_dependency_map.py`.
- [X] T016 [P] Implement GUI-independent core test target setup in `tests/unit/core/test_gui_independent_core.py`.

**Checkpoint**: Foundation complete; user stories can proceed.

---

## Phase 3: User Story 1 - Resume-Safe Core Processing (Priority: P1) 🎯 MVP

**Goal**: Deliver resumable, retry-safe core stage orchestration with deterministic recovery and run-history traceability.

**Independent Test**: Start a job, interrupt after at least one completed stage, restart app, resume from first incomplete stage, and verify no duplicate side effects.

### Tests for User Story 1 (write and fail first)

- [X] T017 [P] [US1] Add interrupted-run resume integration test in `tests/integration/workflows/test_resume_from_first_incomplete_stage.py`.
- [X] T018 [P] [US1] Add retry-policy RED tests (`Retry-After`, backoff+jitter with `1s` initial and `60s` max delay, escalation) in `tests/unit/application/test_retry_controller.py`.
- [X] T019 [P] [US1] Add storage-threshold RED behavior tests for `<20GB` warning, `<10GB` start block, and `<5GB` safe pause in `tests/integration/workflows/test_storage_threshold_policy.py`.
- [X] T020 [P] [US1] Add startup stale-state and post-checkpoint config-change resume-gate RED tests in `tests/integration/workflows/test_resume_safety_guards.py`.

### Implementation for User Story 1

- [X] T021 [US1] Implement stage orchestrator with checkpoint persistence and run-history projection in `src/cvcutter/application/workflows/processing_workflow.py`.
- [X] T022 [US1] Implement resume service selecting first incomplete stage with invalidate-or-cancel gate in `src/cvcutter/application/services/resume_service.py`.
- [X] T023 [US1] Implement retry controller with idempotent operation envelope in `src/cvcutter/application/services/retry_controller.py`.
- [X] T024 [US1] Implement storage safety policy and operator-confirmed unblock gate in `src/cvcutter/application/services/storage_safety_service.py`.
- [X] T025 [US1] Implement startup stale-state recovery and new-job blocking in `src/cvcutter/application/services/startup_recovery_service.py`.
- [X] T026 [US1] Implement config-change detector and decision recorder for resume gating in `src/cvcutter/application/services/config_change_guard_service.py`.

**Checkpoint**: US1 is independently functional and testable (MVP scope).

---

## Phase 4: User Story 2 - Guided Setup and Transparent Progress (Priority: P2)

**Goal**: Provide guided job setup, clear progress/error visibility, and classification guidance flows for operators.

**Independent Test**: A first-time operator configures and launches a job from UI guidance only, and sees stage-by-stage progress plus corrective guidance.

### Tests for User Story 2 (write and fail first)

- [X] T027 [P] [US2] Add setup-wizard validation RED tests in `tests/integration/presentation/test_setup_wizard_validation.py`.
- [X] T028 [P] [US2] Add progress dashboard/run-history timeline and Japanese localization RED tests in `tests/integration/presentation/test_progress_dashboard_state.py`.
- [X] T029 [P] [US2] Add FR-029 threshold RED tests (`top>=70`, `margin>=10`, single-candidate) plus trace-context/no-confident-match checks in `tests/unit/domain/classification/test_content_matching_guidance.py`.
- [X] T030 [P] [US2] Add timestamp-strategy validity RED tests in `tests/unit/domain/classification/test_timestamp_strategy_validity.py`.
- [X] T031 [P] [US2] Add model-availability fallback/block RED tests in `tests/unit/application/test_model_availability_policy.py`.

### Implementation for User Story 2

- [X] T032 [US2] Implement setup wizard viewmodel in `src/cvcutter/presentation/flet_app/viewmodels/setup_wizard_viewmodel.py`.
- [X] T033 [US2] Implement setup wizard screens with inline guidance and externalized Japanese strings in `src/cvcutter/presentation/flet_app/views/setup_wizard_view.py`.
- [X] T034 [US2] Implement progress dashboard and run-history timeline viewmodel in `src/cvcutter/presentation/flet_app/viewmodels/progress_dashboard_viewmodel.py`.
- [X] T035 [US2] Implement confidence scoring policy and classification output payload schema (`strategy`, `top_candidate`, `top_score`, nullable `next_score`, `confidence_state`, `reason_codes`, `trace_context`) in `src/cvcutter/domain/classification/confidence_policy.py`.
- [X] T036 [US2] Implement per-job strategy persistence/restore in `src/cvcutter/application/services/classification_strategy_service.py`.
- [X] T037 [US2] Implement transcription-to-program matching with trace-context output and recovery guidance in `src/cvcutter/application/services/classification_guidance_service.py`.
- [X] T038 [US2] Implement timestamp metadata validator with remediation guidance in `src/cvcutter/domain/classification/timestamp_validator.py`.
- [X] T039 [US2] Implement local model/runtime preflight and reduced-confidence fallback policy before classification in `src/cvcutter/application/services/model_preflight_service.py`.

**Checkpoint**: US2 independently supports guided setup and transparent runtime behavior.

---

## Phase 5: User Story 3 - Accurate Segmenting and Audio Alignment (Priority: P3)

**Goal**: Deliver high-quality segment candidates and synchronization workflows with explicit confidence/review controls.

**Independent Test**: Run validation samples with known boundaries and offsets, then verify quality thresholds and review-gate behavior.

### Tests for User Story 3 (write and fail first)

- [X] T040 [P] [US3] Add multimodal disagreement RED tests in `tests/unit/domain/segmentation/test_multimodal_disagreement_candidates.py`.
- [X] T041 [P] [US3] Add low-confidence confirmation transition RED tests (accept/adjust/reject and unblock) in `tests/integration/workflows/test_low_confidence_confirmation_gate.py`.
- [X] T042 [P] [US3] Add single-source sync path RED tests in `tests/unit/domain/synchronization/test_single_source_sync_paths.py`.
- [X] T043 [P] [US3] Add alignment tolerance RED tests (`80 ms`) in `tests/unit/domain/synchronization/test_alignment_quality_threshold.py`.
- [X] T044 [P] [US3] Add tuning-mode switching RED tests in `tests/integration/presentation/test_tuning_mode_switching.py`.

### Implementation for User Story 3

- [X] T045 [US3] Implement stream-first segmentation pipeline with optional-acceleration detection and CPU fallback in `src/cvcutter/infrastructure/media/segmentation_pipeline.py`.
- [X] T046 [US3] Implement confidence-weighted boundary aggregation in `src/cvcutter/domain/segmentation/boundary_aggregator.py`.
- [X] T047 [US3] Implement per-job low-confidence threshold policy in `src/cvcutter/domain/segmentation/threshold_policy.py`.
- [X] T048 [US3] Implement synchronization branching service (auto-skip/manual-sync) in `src/cvcutter/application/services/synchronization_service.py`.
- [X] T049 [US3] Implement alignment quality evaluator and correction status policy in `src/cvcutter/domain/synchronization/alignment_quality_policy.py`.
- [X] T050 [US3] Implement segment confirmation UI (accept/adjust/reject) with tuning controls and review-status persistence in `src/cvcutter/presentation/flet_app/views/segment_review_view.py`.
- [X] T051 [US3] Implement export/publish readiness gate for unresolved low-confidence reviews and unresolved sync-correction flags in `src/cvcutter/application/services/export_readiness_service.py`.

**Checkpoint**: US3 independently achieves segmentation/sync quality controls and gating.

---

## Phase 6: User Story 4 - Stable Automated Publishing (Priority: P4)

**Goal**: Publish finalized outputs through approved adapters with policy enforcement, schema-safe metadata, and idempotent retry behavior.

**Independent Test**: Publish finalized segments under transient network failures and verify retry recovery within policy window without duplicate publishes.

### Tests for User Story 4 (write and fail first)

- [X] T052 [P] [US4] Add external adapter contract RED tests for operations, mandatory publish fields, `AdapterResult` semantics, and incompatible-version preflight block/remediation behavior in `tests/contract/test_external_integration_adapter_contract.py`.
- [X] T053 [P] [US4] Add publish dedup/retry RED integration tests in `tests/integration/publishing/test_publish_dedup_retry.py`.
- [X] T054 [P] [US4] Add non-approved destination policy RED tests in `tests/unit/domain/publishing/test_destination_policy.py`.
- [X] T055 [P] [US4] Add metadata schema RED contract tests for alias mapping, mixed CSV rejection, JSON version mismatch rejection, unknown future version rejection, unknown-field warnings, field constraints, and success-event emission in `tests/contract/test_metadata_schema_contract.py`.
- [X] T056 [P] [US4] Add format-matrix and opening-title toggle/duration RED integration tests in `tests/integration/media/test_format_and_title_overlay.py`.
- [X] T057 [P] [US4] Add plaintext credential write/read and consent-gate RED tests in `tests/integration/presentation/test_plaintext_credential_consent.py`.

### Implementation for User Story 4

- [X] T058 [US4] Implement approved adapter interfaces with pinned API inventory and full `publish_segment`/`fetch_form_responses`/`classify_content` operations plus `AdapterResult` mapping in `src/cvcutter/infrastructure/integrations/adapters.py`.
- [X] T059 [US4] Implement external provider API-version compatibility preflight service before adapter dispatch in `src/cvcutter/application/services/integration_compatibility_service.py`.
- [X] T060 [US4] Implement idempotent publishing executor with retry telemetry in `src/cvcutter/application/services/publishing_service.py`.
- [X] T061 [US4] Implement provider-and-destination allowlist policy gate for all adapter operations in `src/cvcutter/domain/policies/destination_policy.py`.
- [X] T062 [US4] Implement metadata import normalizer/validator with alias mapping, explicit edge-case handling, version mapping, and metadata-validation success-event emission in `src/cvcutter/application/services/metadata_import_service.py`.
- [X] T063 [US4] Implement segment-to-metadata mapping enforcement in `src/cvcutter/application/services/metadata_mapping_service.py`.
- [X] T064 [US4] Implement export pipeline with format-matrix validation and opening-title rendering in `src/cvcutter/infrastructure/media/export_pipeline.py`.
- [X] T065 [US4] Implement Flet publish workflow viewmodel/controller with credential consent and plaintext config write/read integration in `src/cvcutter/presentation/flet_app/viewmodels/publish_workflow_viewmodel.py`.

**Checkpoint**: US4 independently supports policy-safe automated publishing.

---

## Phase 7: User Story 5 - Install and First Launch (Priority: P5)

**Goal**: Deliver packaged installation and first-launch onboarding for non-engineering users on supported desktop platforms.

**Independent Test**: Install on a clean supported workstation, launch successfully without developer tooling, and complete onboarding to first draft creation.

### Tests for User Story 5 (write and fail first)

- [X] T066 [P] [US5] Add installer and unsupported-startup OS compatibility RED tests in `tests/integration/packaging/test_installer_os_compatibility.py`.
- [X] T067 [P] [US5] Add first-launch onboarding RED tests in `tests/integration/presentation/test_first_launch_onboarding.py`.
- [X] T068 [P] [US5] Add packaged runtime smoke RED tests on clean machines without preinstalled Python/uv in `tests/integration/packaging/test_packaged_runtime_smoke.py`.

### Implementation for User Story 5

- [X] T069 [US5] Implement supported-platform compatibility checker in `src/cvcutter/infrastructure/packaging/platform_compatibility.py`.
- [X] T070 [US5] Implement packaged bootstrap/onboarding handoff in `src/cvcutter/app.py`.
- [X] T071 [US5] Implement onboarding screens and first-draft entry flow in `src/cvcutter/presentation/flet_app/views/onboarding_view.py`.
- [X] T072 [US5] Implement desktop packaging configuration in `build_exe.py`.

**Checkpoint**: US5 independently supports install and first launch.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Finalize cross-story contracts, compliance evidence, and quality gates.

- [X] T073 [P] Add authorization-role workflow regression tests including event-log normalized `operator` assertions in `tests/integration/security/test_authorization_role_workflows.py`.
- [X] T074 [P] Add cleanup-retention contract regression tests in `tests/contract/test_cleanup_retention_contract.py`.
- [X] T075 [P] Add keyboard-only/focus-visibility/contrast RED tests for primary workflows in `tests/integration/presentation/test_accessibility_keyboard_contrast.py`.
- [X] T076 Implement executable-role enforcement policy in `src/cvcutter/domain/policies/authorization_policy.py`.
- [X] T077 Implement cleanup manager with protected-audit rejection and event writes in `src/cvcutter/application/services/cleanup_service.py`.
- [X] T078 Implement cleanup action controller and protected-ledger rejection messaging in `src/cvcutter/presentation/controllers/cleanup_controller.py`.
- [X] T079 Implement keyboard navigation, focus indicators, and contrast-safe theme behavior in `src/cvcutter/presentation/flet_app/views/accessibility_view.py`.
- [X] T080 Produce FR traceability matrix including authorization-role workflow mapping evidence in `specs/002-refactor-concert-tool/checklists/traceability-matrix.md`.
- [X] T081 Add FR-046/FR-047 compliance-scope guard tests in `tests/integration/governance/test_compliance_scope_guard.py`.
- [X] T082 Implement FR-046/FR-047 compliance-scope verification service in `src/cvcutter/application/services/compliance_scope_service.py`.
- [X] T083 Run preliminary `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov` in `specs/002-refactor-concert-tool/checklists/quality-gates.md`.
- [X] T084 Define SC-001..SC-010 measurement protocol and capture templates in `specs/002-refactor-concert-tool/checklists/success-criteria-protocol.md`.
- [X] T085 Prepare SC-001..SC-010 execution scripts and report template in `specs/002-refactor-concert-tool/checklists/success-criteria-report.md`.
- [X] T086 [P] Add processing-event payload regression tests for storage and cleanup event families in `tests/contract/test_processing_event_payloads.py`.
- [X] T087 [P] Add multi-instance lock contention and draft-lock stale-lifecycle (`active -> stale -> released`) end-to-end regression tests in `tests/integration/workflows/test_cross_process_lock_contention.py`.
- [X] T088 Implement Japanese localization catalog coverage across setup/progress/review/publish/onboarding workflows in `src/cvcutter/presentation/flet_app/localization/ja_jp.json`.
- [X] T089 [P] Add optional-acceleration unavailable CPU fallback regression tests in `tests/integration/media/test_cpu_fallback_without_acceleration.py`.
- [X] T090 Implement shared runtime preflight wiring for existing CPU-fallback hooks in packaged execution profiles in `src/cvcutter/application/services/runtime_preflight_service.py`.
- [X] T091 [P] Add append-only immutability and mutation-rejection contract tests in `tests/contract/test_event_retry_payload_and_immutability.py`.
- [X] T092 [P] Add append-only mutation/deletion guard hardening regression tests in `tests/integration/observability/test_event_ledger_append_only.py`.
- [X] T093 Validate `Manual Test Protocol` placeholder completeness and approver ownership in `specs/002-refactor-concert-tool/plan.md`.
- [X] T094 [P] Add recoverability-label and next-action error contract tests in `tests/integration/presentation/test_error_recoverability_labels.py`.
- [X] T095 Implement unified error-guidance mapper for recoverable vs blocking failures in `src/cvcutter/application/services/error_guidance_service.py`.
- [X] T096 [P] Add credential consent/source audit-record tests in `tests/integration/integrations/test_credential_consent_audit.py`.
- [X] T097 Implement credential source and consent audit event persistence hardening in `src/cvcutter/infrastructure/observability/credential_audit_events.py`.
- [X] T098 [P] Add publish.dedup_blocked event contract tests in `tests/contract/test_publish_dedup_blocked_event.py`.
- [X] T099 Implement `publish.dedup_blocked` event emission in `src/cvcutter/application/services/publishing_service.py`.
- [X] T100 Run final `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov` and refresh evidence in `specs/002-refactor-concert-tool/checklists/quality-gates.md`.
- [ ] T101 Execute final SC-001..SC-010 runs plus quickstart/gui-independent validations and publish report in `specs/002-refactor-concert-tool/checklists/success-criteria-report.md`.
- [ ] T102 Update `Manual Test Protocol` with post-execution observed results and pass/fail date in `specs/002-refactor-concert-tool/plan.md`.
- [X] T103 Decommission legacy `customtkinter` entry paths and add migration-completion verification in `src/cvcutter/presentation/legacy_customtkinter_retirement.py`.
- [ ] T104 Produce or fetch CI/release packaged artifact and record provenance for quickstart Section 5 in `specs/002-refactor-concert-tool/checklists/release-artifact.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1; blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2 and defines MVP.
- **Phase 4 (US2)**: Depends on Phase 2 (recommended after US1 for risk-first delivery).
- **Phase 5 (US3)**: Depends on Phase 2 and core orchestration from US1.
- **Phase 6 (US4)**: Depends on US1 + US2 + US3 outputs.
- **Phase 7 (US5)**: Depends on Phase 2 plus runtime prerequisites delivered in US2 (`T039`) and US3 (`T045`).
- **Phase 8 (Polish)**: Depends on all selected user stories.

### User Story Dependencies

- **US1 (P1)**: No story dependency after foundational completion.
- **US2 (P2)**: No hard story dependency after foundational completion.
- **US3 (P3)**: Depends on US1 core workflow orchestration.
- **US4 (P4)**: Depends on US1, US2, and US3 deliverables.
- **US5 (P5)**: Depends on foundational plus US2/US3 runtime prerequisites; independent from US4 publishing behavior.

### Within Each User Story

- Write tests first and confirm failure.
- Prefer implementing domain/policy logic before orchestration/presentation wiring when dependencies allow.
- Complete story-level regression checks before moving to next priority.

### Parallel Opportunities

- Setup and foundational tasks marked `[P]` can run in parallel.
- In each story phase, RED tests marked `[P]` can run in parallel.
- Independent implementation tasks across different files can run in parallel after prerequisites complete.

### Requirement Traceability Strategy

- `T080` produces an explicit FR/NFR/CR/Contract-to-task matrix (one row per requirement) for deterministic acceptance verification.

---

## Parallel Example: User Story 1

```bash
# Parallel RED tests for US1
T017 tests/integration/workflows/test_resume_from_first_incomplete_stage.py
T018 tests/unit/application/test_retry_controller.py
T019 tests/integration/workflows/test_storage_threshold_policy.py
T020 tests/integration/workflows/test_resume_safety_guards.py

```

## Parallel Example: User Story 2

```bash
# Parallel RED tests for US2
T027 tests/integration/presentation/test_setup_wizard_validation.py
T028 tests/integration/presentation/test_progress_dashboard_state.py
T029 tests/unit/domain/classification/test_content_matching_guidance.py
T030 tests/unit/domain/classification/test_timestamp_strategy_validity.py
T031 tests/unit/application/test_model_availability_policy.py

```

## Parallel Example: User Story 3

```bash
# Parallel RED tests for US3
T040 tests/unit/domain/segmentation/test_multimodal_disagreement_candidates.py
T041 tests/integration/workflows/test_low_confidence_confirmation_gate.py
T042 tests/unit/domain/synchronization/test_single_source_sync_paths.py
T043 tests/unit/domain/synchronization/test_alignment_quality_threshold.py
T044 tests/integration/presentation/test_tuning_mode_switching.py

```

## Parallel Example: User Story 4

```bash
# Parallel RED tests for US4
T052 tests/contract/test_external_integration_adapter_contract.py
T053 tests/integration/publishing/test_publish_dedup_retry.py
T054 tests/unit/domain/publishing/test_destination_policy.py
T055 tests/contract/test_metadata_schema_contract.py
T056 tests/integration/media/test_format_and_title_overlay.py
T057 tests/integration/presentation/test_plaintext_credential_consent.py

```

## Parallel Example: User Story 5

```bash
# Parallel RED tests for US5
T066 tests/integration/packaging/test_installer_os_compatibility.py
T067 tests/integration/presentation/test_first_launch_onboarding.py
T068 tests/integration/packaging/test_packaged_runtime_smoke.py

```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate US1 independently (resume/retry/dedup safety).
4. Release MVP candidate for core reliability validation.

### Incremental Delivery

1. Add US2 for guided setup/progress visibility.
2. Add US3 for segmentation/sync quality controls.
3. Add US4 for stable publishing automation.
4. Add US5 for packaged install/onboarding.
5. Finish Phase 8 polish and quality-gate evidence.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. Team completes US1 dependency outputs first.
3. Then split by stories:
   - Engineer A: US2
   - Engineer B: US3
   - Engineer C: US5 (after T039 and T045 are complete)
4. Merge into US4 and final polish once upstream dependencies are stable.

