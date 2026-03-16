# Tasks: CVCutter End-to-End Refactor

**Input**: Design documents from `specs/002-refactor-concert-tool/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Test tasks are required for this feature because `spec.md` mandates TDD evidence (CR-003) and quality-gate validation.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `- [ ] T### [P?] [US?] Description with file path`

- `[P]` means the task can run in parallel (different files, no dependency on incomplete tasks).
- `[US#]` labels appear only in user story phases.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize project structure, tooling, and baseline app shell for refactor work.

- [ ] T001 Create layered package directories in `src/cvcutter/{presentation,application,domain,infrastructure,shared}`.
- [ ] T002 Configure application entry points and `uv` scripts in `pyproject.toml`.
- [ ] T003 [P] Configure lint/type/test tooling defaults in `pyproject.toml`.
- [ ] T004 [P] Create shared test fixtures for SQLite/media stubs in `tests/conftest.py`.
- [ ] T005 [P] Add workflow stage constants and enums in `src/cvcutter/domain/jobs/stages.py`.
- [ ] T006 Create Flet shell bootstrap wiring in `src/cvcutter/app.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core persistence, eventing, and safety primitives that block all user stories.

**⚠️ CRITICAL**: No user story implementation starts before this phase is complete.

- [ ] T007 [P] Add lifecycle transition RED tests for `ProcessingJob` in `tests/unit/domain/jobs/test_processing_job_lifecycle.py`.
- [ ] T008 [P] Add uniqueness RED tests for checkpoint/publish dedup keys in `tests/integration/persistence/test_uniqueness_constraints.py`.
- [ ] T009 [P] Add processing-event envelope RED contract tests in `tests/contract/test_processing_event_contract.py`.
- [ ] T010 Implement `ProcessingJob` aggregate transitions and guards in `src/cvcutter/domain/jobs/processing_job.py`.
- [ ] T011 Implement SQLite base schema for jobs/checkpoints/segments/audio/mapping/publishing/events/locks in `src/cvcutter/infrastructure/persistence/migrations/001_initial_schema.sql`.
- [ ] T012 Implement persistence repositories for core aggregates in `src/cvcutter/infrastructure/persistence/repositories.py`.
- [ ] T013 Implement append-only event ledger writer in `src/cvcutter/infrastructure/observability/event_ledger.py`.
- [ ] T014 Implement workstation active-job + draft-lock management in `src/cvcutter/application/services/lock_service.py`.
- [ ] T015 Implement configuration-change dependency map policy in `src/cvcutter/domain/checkpoints/config_dependency_map.py`.
- [ ] T016 [P] Add GUI-independent core test target setup in `tests/unit/core/test_gui_independent_core.py`.

**Checkpoint**: Foundation complete; user stories can proceed.

---

## Phase 3: User Story 1 - Resume-Safe Core Processing (Priority: P1) 🎯 MVP

**Goal**: Deliver resumable, retry-safe core stage orchestration with deterministic recovery and run-history traceability.

**Independent Test**: Start a job, interrupt after at least one completed stage, restart app, resume from first incomplete stage, and verify no duplicate side effects.

### Tests for User Story 1 (write and fail first)

- [ ] T017 [P] [US1] Add interrupted-run resume integration test in `tests/integration/workflows/test_resume_from_first_incomplete_stage.py`.
- [ ] T018 [P] [US1] Add retry-policy RED tests (`Retry-After`, backoff+jitter, escalation) in `tests/unit/application/test_retry_controller.py`.
- [ ] T019 [P] [US1] Add storage-threshold RED behavior tests in `tests/integration/workflows/test_storage_threshold_policy.py`.
- [ ] T020 [P] [US1] Add startup stale-state and post-checkpoint config-change resume-gate RED tests in `tests/integration/workflows/test_resume_safety_guards.py`.

### Implementation for User Story 1

- [ ] T021 [US1] Implement stage orchestrator with checkpoint persistence and run-history projection in `src/cvcutter/application/workflows/processing_workflow.py`.
- [ ] T022 [US1] Implement resume service selecting first incomplete stage with invalidate-or-cancel gate in `src/cvcutter/application/services/resume_service.py`.
- [ ] T023 [US1] Implement retry controller with idempotent operation envelope in `src/cvcutter/application/services/retry_controller.py`.
- [ ] T024 [US1] Implement storage safety policy and operator-confirmed unblock gate in `src/cvcutter/application/services/storage_safety_service.py`.
- [ ] T025 [US1] Implement startup stale-state recovery and new-job blocking in `src/cvcutter/application/services/startup_recovery_service.py`.
- [ ] T026 [US1] Implement config-change detector and decision recorder for resume gating in `src/cvcutter/application/services/config_change_guard_service.py`.

**Checkpoint**: US1 is independently functional and testable (MVP scope).

---

## Phase 4: User Story 2 - Guided Setup and Transparent Progress (Priority: P2)

**Goal**: Provide guided job setup, clear progress/error visibility, and classification guidance flows for operators.

**Independent Test**: A first-time operator configures and launches a job from UI guidance only, and sees stage-by-stage progress plus corrective guidance.

### Tests for User Story 2 (write and fail first)

- [ ] T027 [P] [US2] Add setup-wizard validation RED tests in `tests/integration/presentation/test_setup_wizard_validation.py`.
- [ ] T028 [P] [US2] Add progress dashboard RED tests in `tests/integration/presentation/test_progress_dashboard_state.py`.
- [ ] T029 [P] [US2] Add content-matching trace-context and no-confident-match RED tests in `tests/unit/domain/classification/test_content_matching_guidance.py`.
- [ ] T030 [P] [US2] Add timestamp-strategy validity RED tests in `tests/unit/domain/classification/test_timestamp_strategy_validity.py`.
- [ ] T031 [P] [US2] Add model-availability fallback/block RED tests in `tests/unit/application/test_model_availability_policy.py`.

### Implementation for User Story 2

- [ ] T032 [US2] Implement setup wizard viewmodel in `src/cvcutter/presentation/flet_app/viewmodels/setup_wizard_viewmodel.py`.
- [ ] T033 [US2] Implement setup wizard screens with inline guidance in `src/cvcutter/presentation/flet_app/views/setup_wizard_view.py`.
- [ ] T034 [US2] Implement progress dashboard viewmodel in `src/cvcutter/presentation/flet_app/viewmodels/progress_dashboard_viewmodel.py`.
- [ ] T035 [US2] Implement confidence scoring policy (`>=70` and `+10 margin`) in `src/cvcutter/domain/classification/confidence_policy.py`.
- [ ] T036 [US2] Implement per-job strategy persistence/restore in `src/cvcutter/application/services/classification_strategy_service.py`.
- [ ] T037 [US2] Implement transcription-to-program matching with trace-context output and recovery guidance in `src/cvcutter/application/services/classification_guidance_service.py`.
- [ ] T038 [US2] Implement timestamp metadata validator with remediation guidance in `src/cvcutter/domain/classification/timestamp_validator.py`.
- [ ] T039 [US2] Implement model preflight and reduced-confidence fallback policy in `src/cvcutter/application/services/model_preflight_service.py`.

**Checkpoint**: US2 independently supports guided setup and transparent runtime behavior.

---

## Phase 5: User Story 3 - Accurate Segmenting and Audio Alignment (Priority: P3)

**Goal**: Deliver high-quality segment candidates and synchronization workflows with explicit confidence/review controls.

**Independent Test**: Run validation samples with known boundaries and offsets, then verify quality thresholds and review-gate behavior.

### Tests for User Story 3 (write and fail first)

- [ ] T040 [P] [US3] Add multimodal disagreement RED tests in `tests/unit/domain/segmentation/test_multimodal_disagreement_candidates.py`.
- [ ] T041 [P] [US3] Add low-confidence review gate RED tests in `tests/integration/workflows/test_low_confidence_confirmation_gate.py`.
- [ ] T042 [P] [US3] Add single-source sync path RED tests in `tests/unit/domain/synchronization/test_single_source_sync_paths.py`.
- [ ] T043 [P] [US3] Add alignment tolerance RED tests (`80 ms`) in `tests/unit/domain/synchronization/test_alignment_quality_threshold.py`.
- [ ] T044 [P] [US3] Add tuning-mode switching RED tests in `tests/integration/presentation/test_tuning_mode_switching.py`.

### Implementation for User Story 3

- [ ] T045 [US3] Implement stream-first segmentation pipeline adapter in `src/cvcutter/infrastructure/media/segmentation_pipeline.py`.
- [ ] T046 [US3] Implement confidence-weighted boundary aggregation in `src/cvcutter/domain/segmentation/boundary_aggregator.py`.
- [ ] T047 [US3] Implement per-job low-confidence threshold policy in `src/cvcutter/domain/segmentation/threshold_policy.py`.
- [ ] T048 [US3] Implement synchronization branching service (auto-skip/manual-sync) in `src/cvcutter/application/services/synchronization_service.py`.
- [ ] T049 [US3] Implement alignment quality evaluator and correction status policy in `src/cvcutter/domain/synchronization/alignment_quality_policy.py`.
- [ ] T050 [US3] Implement simple/waveform tuning UI in `src/cvcutter/presentation/flet_app/views/audio_tuning_view.py`.
- [ ] T051 [US3] Implement export/publish readiness gate for unresolved review items in `src/cvcutter/application/services/export_readiness_service.py`.

**Checkpoint**: US3 independently achieves segmentation/sync quality controls and gating.

---

## Phase 6: User Story 4 - Stable Automated Publishing (Priority: P4)

**Goal**: Publish finalized outputs through approved adapters with policy enforcement, schema-safe metadata, and idempotent retry behavior.

**Independent Test**: Publish finalized segments under transient network failures and verify retry recovery within policy window without duplicate publishes.

### Tests for User Story 4 (write and fail first)

- [ ] T052 [P] [US4] Add external adapter contract RED tests in `tests/contract/test_external_integration_adapter_contract.py`.
- [ ] T053 [P] [US4] Add publish dedup/retry RED integration tests in `tests/integration/publishing/test_publish_dedup_retry.py`.
- [ ] T054 [P] [US4] Add non-approved destination policy RED tests in `tests/unit/domain/publishing/test_destination_policy.py`.
- [ ] T055 [P] [US4] Add metadata schema compatibility RED contract tests in `tests/contract/test_metadata_schema_contract.py`.
- [ ] T056 [P] [US4] Add supported format matrix RED integration tests in `tests/integration/media/test_format_support_matrix.py`.
- [ ] T057 [P] [US4] Add plaintext credential consent-gate RED tests in `tests/integration/presentation/test_plaintext_credential_consent.py`.

### Implementation for User Story 4

- [ ] T058 [US4] Implement approved adapter interfaces with pinned API inventory in `src/cvcutter/infrastructure/integrations/adapters.py`.
- [ ] T059 [US4] Implement integration compatibility preflight service in `src/cvcutter/application/services/integration_compatibility_service.py`.
- [ ] T060 [US4] Implement idempotent publishing executor with retry telemetry in `src/cvcutter/application/services/publishing_service.py`.
- [ ] T061 [US4] Implement destination allowlist policy gate in `src/cvcutter/domain/policies/destination_policy.py`.
- [ ] T062 [US4] Implement metadata import normalizer/validator with version mapping in `src/cvcutter/application/services/metadata_import_service.py`.
- [ ] T063 [US4] Implement segment-to-metadata mapping enforcement in `src/cvcutter/application/services/metadata_mapping_service.py`.
- [ ] T064 [US4] Implement export pipeline with format-matrix validation and opening-title rendering in `src/cvcutter/infrastructure/media/export_pipeline.py`.
- [ ] T065 [US4] Implement credential risk-warning and consent UI flow in `src/cvcutter/presentation/flet_app/views/credential_risk_dialog.py`.

**Checkpoint**: US4 independently supports policy-safe automated publishing.

---

## Phase 7: User Story 5 - Install and First Launch (Priority: P5)

**Goal**: Deliver packaged installation and first-launch onboarding for non-engineering users on supported desktop platforms.

**Independent Test**: Install on a clean supported workstation, launch successfully without developer tooling, and complete onboarding to first draft creation.

### Tests for User Story 5 (write and fail first)

- [ ] T066 [P] [US5] Add installer OS compatibility RED tests in `tests/integration/packaging/test_installer_os_compatibility.py`.
- [ ] T067 [P] [US5] Add first-launch onboarding RED tests in `tests/integration/presentation/test_first_launch_onboarding.py`.
- [ ] T068 [P] [US5] Add packaged runtime smoke RED tests in `tests/integration/packaging/test_packaged_runtime_smoke.py`.

### Implementation for User Story 5

- [ ] T069 [US5] Implement supported-platform compatibility checker in `src/cvcutter/infrastructure/packaging/platform_compatibility.py`.
- [ ] T070 [US5] Implement packaged bootstrap/onboarding handoff in `src/cvcutter/app.py`.
- [ ] T071 [US5] Implement onboarding screens and first-draft entry flow in `src/cvcutter/presentation/flet_app/views/onboarding_view.py`.
- [ ] T072 [US5] Implement desktop packaging configuration in `build_exe.py`.

**Checkpoint**: US5 independently supports install and first launch.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Finalize cross-story contracts, compliance evidence, and quality gates.

- [ ] T073 [P] Add authorization-role contract regression tests in `tests/contract/test_authorization_role_contract.py`.
- [ ] T074 [P] Add cleanup-retention contract regression tests in `tests/contract/test_cleanup_retention_contract.py`.
- [ ] T075 [P] Add processing-event payload regression tests in `tests/contract/test_processing_event_payloads.py`.
- [ ] T076 Implement executable-role enforcement policy in `src/cvcutter/domain/policies/authorization_policy.py`.
- [ ] T077 Implement cleanup manager with protected-audit rejection and event writes in `src/cvcutter/application/services/cleanup_service.py`.
- [ ] T078 Implement cleanup action controller and protected-ledger rejection messaging in `src/cvcutter/presentation/flet_app/controllers/cleanup_controller.py`.
- [ ] T079 Update Japanese localization resource coverage in `src/cvcutter/presentation/flet_app/localization/ja_jp.json`.
- [ ] T080 Produce FR traceability matrix in `specs/002-refactor-concert-tool/checklists/traceability-matrix.md`.
- [ ] T081 Add FR-046 compliance-scope guard tests in `tests/integration/governance/test_compliance_scope_guard.py`.
- [ ] T082 Implement compliance-scope verification service in `src/cvcutter/application/services/compliance_scope_service.py`.
- [ ] T083 Run `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov` and record outputs in `specs/002-refactor-concert-tool/checklists/quality-gates.md`.
- [ ] T084 Define SC-001..SC-010 measurement protocol and capture templates in `specs/002-refactor-concert-tool/checklists/success-criteria-protocol.md`.
- [ ] T085 Execute SC-001..SC-010 runs plus quickstart/gui-independent validations and publish report in `specs/002-refactor-concert-tool/checklists/success-criteria-report.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1; blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2 and defines MVP.
- **Phase 4 (US2)**: Depends on Phase 2 (recommended after US1 for risk-first delivery).
- **Phase 5 (US3)**: Depends on Phase 2 and core orchestration from US1.
- **Phase 6 (US4)**: Depends on US1 + US2 + US3 outputs.
- **Phase 7 (US5)**: Depends on Phase 2; can run in parallel with US3/US4 once onboarding dependencies are ready.
- **Phase 8 (Polish)**: Depends on all selected user stories.

### User Story Dependencies

- **US1 (P1)**: No story dependency after foundational completion.
- **US2 (P2)**: No hard story dependency after foundational completion.
- **US3 (P3)**: Depends on US1 core workflow orchestration.
- **US4 (P4)**: Depends on US1, US2, and US3 deliverables.
- **US5 (P5)**: Depends on foundational/runtime setup; independent from publishing behavior.

### Within Each User Story

- Write tests first and confirm failure.
- Implement domain/policy logic before orchestration/presentation wiring.
- Complete story-level regression checks before moving to next priority.

### Parallel Opportunities

- Setup and foundational tasks marked `[P]` can run in parallel.
- In each story phase, RED tests marked `[P]` can run in parallel.
- Independent implementation tasks across different files can run in parallel after prerequisites complete.

---

## Parallel Example: User Story 1

```bash
# Parallel RED tests for US1
T017 tests/integration/workflows/test_resume_from_first_incomplete_stage.py
T018 tests/unit/application/test_retry_controller.py
T019 tests/integration/workflows/test_storage_threshold_policy.py
T020 tests/integration/workflows/test_resume_safety_guards.py

# Parallel implementation after orchestrator foundation
T023 src/cvcutter/application/services/retry_controller.py
T024 src/cvcutter/application/services/storage_safety_service.py
T025 src/cvcutter/application/services/startup_recovery_service.py
```

## Parallel Example: User Story 2

```bash
# Parallel RED tests for US2
T027 tests/integration/presentation/test_setup_wizard_validation.py
T028 tests/integration/presentation/test_progress_dashboard_state.py
T029 tests/unit/domain/classification/test_content_matching_guidance.py
T030 tests/unit/domain/classification/test_timestamp_strategy_validity.py
T031 tests/unit/application/test_model_availability_policy.py

# Parallel implementation after shared UI/viewmodel wiring
T035 src/cvcutter/domain/classification/confidence_policy.py
T038 src/cvcutter/domain/classification/timestamp_validator.py
T039 src/cvcutter/application/services/model_preflight_service.py
```

## Parallel Example: User Story 3

```bash
# Parallel RED tests for US3
T040 tests/unit/domain/segmentation/test_multimodal_disagreement_candidates.py
T041 tests/integration/workflows/test_low_confidence_confirmation_gate.py
T042 tests/unit/domain/synchronization/test_single_source_sync_paths.py
T043 tests/unit/domain/synchronization/test_alignment_quality_threshold.py
T044 tests/integration/presentation/test_tuning_mode_switching.py

# Parallel implementation in separate modules
T046 src/cvcutter/domain/segmentation/boundary_aggregator.py
T049 src/cvcutter/domain/synchronization/alignment_quality_policy.py
T050 src/cvcutter/presentation/flet_app/views/audio_tuning_view.py
```

## Parallel Example: User Story 4

```bash
# Parallel RED tests for US4
T052 tests/contract/test_external_integration_adapter_contract.py
T053 tests/integration/publishing/test_publish_dedup_retry.py
T054 tests/unit/domain/publishing/test_destination_policy.py
T055 tests/contract/test_metadata_schema_contract.py
T056 tests/integration/media/test_format_support_matrix.py
T057 tests/integration/presentation/test_plaintext_credential_consent.py

# Parallel implementation after adapter contracts are stable
T061 src/cvcutter/domain/policies/destination_policy.py
T062 src/cvcutter/application/services/metadata_import_service.py
T064 src/cvcutter/infrastructure/media/export_pipeline.py
T065 src/cvcutter/presentation/flet_app/views/credential_risk_dialog.py
```

## Parallel Example: User Story 5

```bash
# Parallel RED tests for US5
T066 tests/integration/packaging/test_installer_os_compatibility.py
T067 tests/integration/presentation/test_first_launch_onboarding.py
T068 tests/integration/packaging/test_packaged_runtime_smoke.py

# Parallel implementation in packaging/presentation
T069 src/cvcutter/infrastructure/packaging/platform_compatibility.py
T071 src/cvcutter/presentation/flet_app/views/onboarding_view.py
T072 build_exe.py + pyproject.toml
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
2. Then split by stories:
   - Engineer A: US2
   - Engineer B: US3
   - Engineer C: US5
3. Merge into US4 and final polish once upstream dependencies are stable.
