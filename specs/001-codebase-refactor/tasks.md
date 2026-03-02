# Tasks: CVCutter Full Architecture Refactor

**Input**: Design documents from `/specs/001-codebase-refactor/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md, contracts/

## Constitution Compliance Gate

*GATE: Must pass before task execution begins.*

- [X] Non-negotiable architecture-boundary and test-first requirements are explicit.
- [X] Every behavior-changing task has failing tests first, including setup/foundation and integration coverage for cross-module workflows.
- [X] Tasks include local-first, observability/resume, migration/regeneration, and module-size enforcement where applicable.
- [X] Tasks include constitution compliance evidence and independent review evidence before merge/deploy.

**Tests**: Tests are MANDATORY in this plan (CA-002). Every behavior-changing task sequence starts with failing tests.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize project structure, tooling, and guardrails required by constitution gates.

- [X] T001 Create four-layer package skeleton in src/cvcutter/{domain,application,infrastructure,presentation,shared}/__init__.py
- [X] T002 Configure application entrypoint and script in src/cvcutter/main.py and pyproject.toml
- [X] T003 [P] Add test bootstrap and fixtures in tests/conftest.py
- [X] T004 [P] Add lint/type/test commands and coverage config in pyproject.toml
- [X] T005 [P] Add module-size guard script in tools/check_module_size.py
- [X] T006 [P] Add quality-gate CI workflow for ruff/pyright/pytest/module-size in .github/workflows/quality-gates.yml
- [X] T007 [P] Add model/data packaging manifest updates in ./CVCutter.spec and ./build_exe.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement shared contracts, core domain models, persistence boundaries, and migration/logging foundations that block all user stories.

**⚠️ CRITICAL**: No user story work starts until this phase completes.

### Foundational Tests First

- [X] T008 Write failing architecture-boundary import tests in tests/unit/test_architecture_boundaries.py
- [X] T009 [P] Write failing service-contract conformance tests for core ports in tests/contract/test_core_service_contracts.py
- [X] T010 [P] Write failing migration compatibility tests for legacy config/upload files in tests/unit/application/test_migration_service.py
- [X] T011 [P] Write failing structured-logging schema tests in tests/unit/infrastructure/test_structured_logger.py
- [X] T107 [P] Write failing infrastructure unit tests for config and FFmpeg adapters in tests/unit/infrastructure/{test_json_config.py,test_ffmpeg_transcoder.py}
- [X] T124 [P] Write failing checkpoint dependency-graph traversal tests (cascade scope and deterministic ordering) in tests/unit/application/test_checkpoint_manager.py

### Foundational Implementation

- [X] T012 Implement shared enums/value objects in src/cvcutter/shared/types.py
- [X] T013 [P] Implement hashing/time utility helpers in src/cvcutter/shared/{hashing.py,time_utils.py}
- [X] T014 Implement core domain entities for project/segment/checkpoint/upload in src/cvcutter/domain/models/{project.py,segment.py,checkpoint.py,upload.py}
- [X] T015 [P] Implement metadata entities and dictionary metadata model in src/cvcutter/domain/models/{metadata.py,dictionary.py}
- [X] T016 Implement domain service protocols and DTOs in src/cvcutter/domain/services/{types.py,video_io.py,model_runner.py,checkpoint_store.py,project_store.py,quota_state_store.py,pdf_text_extractor.py,music_lookup.py,form_data_service.py,upload_service.py,credential_store.py,ai_enrichment.py}
- [X] T017 Implement JSON persistence adapters for project/checkpoint/quota/config/credentials in src/cvcutter/infrastructure/persistence/{json_project_store.py,json_checkpoint_store.py,json_quota_state_store.py,json_config.py,json_credential_store.py}
- [X] T018 [P] Implement structured JSON logger adapter in src/cvcutter/infrastructure/logging/structured_logger.py
- [X] T019 Implement migration orchestration for legacy files in src/cvcutter/application/migration_service.py
- [X] T020 Implement application checkpoint dependency graph manager in src/cvcutter/application/checkpoint_manager.py

**Checkpoint**: Foundation complete; user stories can begin.

---

## Phase 3: User Story 1 - Baseline Concert Processing (Priority: P1)

**Goal**: Process one or more concert videos (with optional external audio) into export-ready performance segments using baseline boundary detection.

**Independent Test**: Run a sample concert (>=3 performances), process end-to-end, and verify segmented exports with synchronized audio.

### Tests for User Story 1 (MANDATORY)

- [X] T021 [P] [US1] Write failing unit tests for project loading and state transitions in tests/unit/domain/test_models.py
- [X] T022 [P] [US1] Write failing integration test for load-to-export workflow with baseline boundary generation, per-segment export checkpoint writes, and successful-run FR-046 auto-clean behavior in tests/integration/test_video_to_export.py
- [X] T023 [P] [US1] Write failing contract tests for VideoIOService concatenate/export behavior in tests/contract/test_video_io_contract.py
- [X] T127 [P] [US1] Write failing early SC-001 processing-speed smoke benchmark test scaffold in tests/integration/test_processing_benchmarks.py
- [X] T104 [P] [US1] Write failing unit tests for audio sync and checkpoint domain behavior in tests/unit/domain/{test_audio_sync.py,test_checkpoint.py}
- [X] T111 [US1] Write failing unit tests for manual boundary adjust/split domain rules in tests/unit/domain/test_models.py

### Implementation for User Story 1

- [X] T024 [P] [US1] Implement FFmpeg probe/concatenate/extract/export adapter in src/cvcutter/infrastructure/ffmpeg/transcoder.py
- [X] T025 [P] [US1] Implement GPU capability detection adapter in src/cvcutter/infrastructure/ffmpeg/gpu_detect.py
- [X] T026 [P] [US1] Implement audio offset detection logic in src/cvcutter/domain/audio/sync.py
- [X] T121 [P] [US1] Implement provisional domain audio-energy boundary detector for baseline segmentation in src/cvcutter/domain/detection/audio_energy.py
- [X] T112 [P] [US1] Implement manual boundary adjustment and split-segment domain logic (index reassignment, signal partitioning, checkpoint re-addressing hooks) in src/cvcutter/domain/models/segment.py
- [X] T027 [US1] Implement baseline processing orchestrator stages (concatenate/basic-detect/sync/ready-for-export/export) with configurable audio mix and domain-detector invocation for provisional segments in src/cvcutter/application/pipeline.py
- [X] T028 [US1] Implement segment export status handling, per-segment export checkpoint writes, and persistence wiring in src/cvcutter/application/pipeline.py, including successful-run temporary artifact auto-clean trigger per FR-046 policy
- [X] T029 [US1] Add process progress event DTOs and callbacks in src/cvcutter/domain/services/types.py

**Checkpoint**: US1 delivers a functioning baseline processing pipeline with provisional segmentation.

---

## Phase 4: User Story 2 - Resume Interrupted Processing (Priority: P1)

**Goal**: Resume interrupted processing deterministically from valid checkpoints with invalidation when inputs/config/models change.

**Independent Test**: Interrupt after partial export, restart app, and confirm resume starts from the next incomplete segment.

### Tests for User Story 2 (MANDATORY)

- [X] T030 [P] [US2] Write failing unit tests for checkpoint validation/invalidation cascade and resume-vs-restart prompt behavior in tests/unit/application/test_checkpoint_manager.py
- [X] T031 [P] [US2] Write failing integration resume test with forced interruption and explicit restart-from-scratch path, including SC-004 resumed-time <50% of full reprocess, in tests/integration/test_video_to_export.py
- [X] T032 [P] [US2] Write failing persistence tests for checkpoint lifecycle, cleanup policy, and purge/retention controls in tests/unit/infrastructure/test_json_checkpoint_store.py
- [X] T105 [P] [US2] Write failing pipeline resume/restart flow tests in tests/unit/application/test_pipeline.py, including FR-040 checkpoint-write verification for concatenation/detection/audio-sync/per-segment-export stages
- [X] T113 [P] [US2] Write failing tests for single-active-job enforcement and mid-job config-change apply-at-next-boundary behavior in tests/unit/application/test_pipeline.py

### Implementation for User Story 2

- [X] T033 [P] [US2] Wire checkpoint save/load/invalidate trigger orchestration in src/cvcutter/application/checkpoint_manager.py using the foundational json_checkpoint_store adapter
- [X] T034 [P] [US2] Implement explicit resume decision and restart flow (user-choice driven) in src/cvcutter/application/checkpoint_manager.py
- [X] T035 [US2] Integrate stage-level checkpoint writes/resume hooks and apply config changes from next segment boundary (or next stage start) in src/cvcutter/application/pipeline.py
- [X] T036 [US2] Implement deterministic invalidation by input/config/model hashes in src/cvcutter/application/checkpoint_manager.py
- [X] T037 [US2] Add stage-transition structured logging (decision reasons) in src/cvcutter/application/pipeline.py
- [X] T114 [US2] Implement one-active-job concurrency guard and project-scoped isolation in src/cvcutter/application/pipeline.py

**Checkpoint**: US2 can resume safely and reproducibly.

---

## Phase 5: User Story 3 - Accurate Performance Segment Detection (Priority: P1)

**Goal**: Detect performance boundaries using multimodal local detection (YOLO + audio energy + audio classifier) with audio-only fallback.

**Independent Test**: Run reference videos with known boundaries and verify recall/boundary metrics for both full and audio-only modes.

### Tests for User Story 3 (MANDATORY)

- [X] T038 [P] [US3] Write failing unit tests for multimodal boundary fusion logic and visual-signal processing expectations in tests/unit/domain/test_detection.py
- [X] T039 [US3] Write failing unit tests for audio classifier and energy channel behavior in tests/unit/domain/test_detection.py
- [X] T040 [P] [US3] Write failing benchmark integration tests for SC-002 thresholds using one-to-one highest-overlap matching on a >=3-recording ground-truth reference set, with boundary accuracy computed as the fraction of matched detected segments whose start/end are both within tolerance (full mode: recall/boundary >=90% within +-5s; audio-only mode: recall/boundary >=80% within +-8s), including runtime YOLO-unavailable fallback that emits `audio_only` provenance in tests/integration/test_detection_benchmarks.py

### Implementation for User Story 3

- [X] T041 [P] [US3] Enhance audio energy boundary detector for multimodal fusion calibration and SC-002 benchmark compliance in src/cvcutter/domain/detection/audio_energy.py
- [X] T042 [P] [US3] Implement audio content classification logic in src/cvcutter/domain/detection/audio_classifier.py
- [X] T043 [P] [US3] Implement visual detection signal processing in src/cvcutter/domain/detection/visual_detector.py
- [X] T044 [US3] Implement multimodal fusion/state-machine detector in src/cvcutter/domain/detection/detector.py
- [X] T045 [P] [US3] Implement YOLO inference adapter in src/cvcutter/infrastructure/models/yolo_runner.py
- [X] T046 [P] [US3] Implement ONNX audio classifier adapter in src/cvcutter/infrastructure/models/audio_classifier_runner.py
- [X] T047 [US3] Integrate detector stage with YOLO toggle handling and runtime-unavailable fallback in src/cvcutter/application/pipeline.py, emitting detection-mode provenance (`full`/`audio_only`) and reduced-accuracy notice metadata for downstream UI state

**Checkpoint**: US3 detection meets defined quality targets.

---

## Phase 6: User Story 4 - Map Videos to Performance Metadata (Priority: P2)

**Goal**: Map exported segments to program/form metadata using transcription, PDF parsing, lookup, and manual correction support.

**Independent Test**: Provide concert with MC, program PDF, and optional forms; verify >=80% automatic matches and manual correction path.

### Tests for User Story 4 (MANDATORY)

- [X] T048 [P] [US4] Write failing unit tests for transcription/sequential/lookup fusion scoring in tests/unit/domain/test_mapping.py
- [X] T049 [P] [US4] Write failing contract tests for PDF extractor/music lookup/form data ports in tests/contract/test_mapping_service_contracts.py
- [X] T050 [P] [US4] Write failing integration test for detect-to-mapping workflow in tests/integration/test_segment_to_mapping.py
- [X] T106 [P] [US4] Write failing unit tests for mapping workflow state transitions, including FR-040 mapping-completion checkpoint writes, in tests/unit/application/test_mapping_workflow.py
- [X] T115 [P] [US4] Write failing mapping-accuracy benchmark tests with separate fixture sets and manual ground-truth scoring (SC-003: MC-announcement + program-PDF >=80% overall; US4-AS2: sequential mapping with dedicated PDF-order fixtures >=90%) in tests/integration/test_mapping_benchmarks.py
- [X] T116 [P] [US4] Write failing Gemini contract tests for failure-aware behavior in tests/contract/test_gemini_contract.py
- [X] T119 [P] [US4] Write failing Forms/Sheets contract tests in tests/contract/{test_forms_contract.py,test_sheets_contract.py}

### Implementation for User Story 4

- [X] T051 [P] [US4] Implement PDF normalization and program-entry extraction logic in src/cvcutter/domain/mapping/pdf_extraction.py
- [X] T052 [P] [US4] Implement Whisper transcription matching signals in src/cvcutter/domain/mapping/transcription.py
- [X] T053 [P] [US4] Implement deterministic form-response weighted matcher in src/cvcutter/domain/mapping/form_matching.py
- [X] T054 [P] [US4] Implement dictionary lookup scoring logic in src/cvcutter/domain/mapping/music_lookup.py
- [X] T056 [P] [US4] Implement local PDF extraction adapter in src/cvcutter/infrastructure/pdf/local_extractor.py
- [X] T057 [P] [US4] Implement Whisper transcription adapter in src/cvcutter/infrastructure/models/whisper_runner.py
- [X] T058 [P] [US4] Implement bundled SQLite dictionary adapter in src/cvcutter/infrastructure/music/sqlite_lookup.py
- [X] T059 [P] [US4] Implement CSV and remote form ingestion adapters in src/cvcutter/infrastructure/{csv/form_csv_loader.py,google/forms_client.py,google/sheets_client.py,forms/form_data_service.py}
- [X] T060 [P] [US4] Implement optional Gemini enrichment adapter with graceful fallback and manual override support in src/cvcutter/infrastructure/gemini/client.py
- [X] T055 [US4] Implement composite mapping and confidence strategy in src/cvcutter/domain/mapping/composite_mapper.py
- [X] T061 [US4] Implement mapping workflow orchestration and persistence integration in src/cvcutter/application/mapping_workflow.py, including FR-040 mapping-completion checkpoint writes

**Checkpoint**: US4 mapping is complete and manually correctable.

---

## Phase 7: User Story 5 - Modern, Responsive User Interface (Priority: P2)

**Goal**: Deliver responsive Flet workflow UI (Load → Process → Preview/Map → Upload → Settings) with non-blocking operations.

**Independent Test**: Walk full workflow and verify UI responsiveness, progress visibility, and actionable errors.

### Tests for User Story 5 (MANDATORY)

- [X] T062 [P] [US5] Write failing view-model unit tests for command/state transitions and FR-012 reduced-accuracy notice propagation based on detection output provenance (`audio_only`), covering both settings toggle-disabled and runtime-fallback paths, in tests/unit/presentation/test_viewmodels.py
- [X] T063 [P] [US5] Write failing integration UI workflow test verifying FR-063 preview layout (thumbnails + timecodes + metadata side-by-side) with widget-tree layout assertions in tests/integration/test_ui_workflow.py
- [X] T064 [P] [US5] Write failing responsiveness/progress callback tests (SC-006 <=500ms interaction, <=1s preview response, <=3s initial load) in tests/unit/presentation/test_async_updates.py

### Implementation for User Story 5

- [X] T065 [P] [US5] Implement Flet app shell and route/navigation container in src/cvcutter/presentation/app.py
- [X] T066 [P] [US5] Implement load/process/preview/upload/settings view-models including boundary adjust/split, cloud-override visibility, retention/purge controls, and resume/restart prompts in src/cvcutter/presentation/viewmodels/{load_vm.py,process_vm.py,preview_vm.py,upload_vm.py,settings_vm.py}
- [X] T067 [P] [US5] Implement load/process/preview/upload/settings Flet views including boundary split UI, artifact lifecycle controls, FR-063 preview layout (thumbnails + timecodes + metadata side-by-side), and FR-012 reduced-accuracy notice banner sourced from detection-mode provenance (`audio_only`) in src/cvcutter/presentation/views/{load_view.py,process_view.py,preview_view.py,upload_view.py,settings_view.py}
- [X] T068 [US5] Wire view-models to application workflows with background tasks in src/cvcutter/presentation/app.py
- [X] T069 [US5] Implement typed user-facing error translation for domain/application exceptions in src/cvcutter/presentation/viewmodels/process_vm.py

**Checkpoint**: US5 UI is functional, responsive, and workflow-guided.

---

## Phase 8: User Story 6 - YouTube Upload with Quota Management (Priority: P2)

**Goal**: Upload mapped segments with resumable transfers, quota tracking/queueing, playlist support, and auto-resume at quota reset/next launch.

**Independent Test**: Upload 3 prepared segments with metadata; verify status/URLs/playlist and quota-respecting behavior.

### Tests for User Story 6 (MANDATORY)

- [X] T070 [P] [US6] Write failing contract tests for upload and playlist API behavior (FR-050 metadata completeness + FR-052 resumable semantics: valid-session resume and invalid-session restart-from-0 with surfaced reason + FR-053 playlist create/assign behavior) in tests/contract/test_youtube_contract.py
- [X] T071 [P] [US6] Write failing unit tests for FR-051 quota reset scheduler/queue policy and FR-040 per-upload checkpoint write semantics in tests/unit/application/test_upload_workflow.py
- [X] T072 [P] [US6] Write failing integration test for upload-with-quota and auto-resume, including SC-011 fixed benchmark (<2h for 6 upload-ready segments under defined network profile), FR-051 quota queueing, network-loss retry exhaustion behavior (pause failed upload, continue queue), FR-052 invalidated-resumable-session fallback (restart from 0 with surfaced diagnostic reason persisted and visible after restart), FR-054 per-video status + completed-video URL display verification, and FR-055 next-launch auto-resume when app was closed at reset, in tests/integration/test_upload_with_quota.py

### Implementation for User Story 6

- [X] T073 [P] [US6] Implement YouTube upload/playlist adapter with resumable URI support in src/cvcutter/infrastructure/youtube/client.py
- [X] T074 [P] [US6] Implement OAuth authentication helper in src/cvcutter/infrastructure/youtube/auth.py
- [X] T076 [P] [US6] Implement/extend global quota-state persistence adapter APIs for upload workflow consumption in src/cvcutter/infrastructure/persistence/json_quota_state_store.py
- [X] T075 [US6] Implement quota-aware upload workflow and retry/backoff policy with per-item retry exhaustion handling (pause failed upload, continue remaining queue), FR-052 invalidated-session fallback diagnostics propagation/persistence (reason, timestamp, retry decision), FR-053 deterministic playlist assignment policy, and FR-040 per-upload checkpoint writes in src/cvcutter/application/upload_workflow.py
- [X] T077 [US6] Implement queued-upload auto-resume scheduler (PT00:00 + next-launch recovery) in src/cvcutter/application/upload_workflow.py
- [X] T078 [US6] Integrate upload workflow with upload view-model/status model updates in src/cvcutter/presentation/viewmodels/upload_vm.py, including FR-054 per-video status and completed-video YouTube URL display wiring

**Checkpoint**: US6 completes reliable publish flow with quota safety.

---

## Phase 9: User Story 7 - Install and Run as Desktop Application (Priority: P3)

**Goal**: Produce a standalone Windows installer bundling runtime and local models, with clean upgrade behavior.

**Independent Test**: Install on clean Windows machine without Python, launch app, and complete basic processing.

### Tests for User Story 7 (MANDATORY)

- [X] T079 [P] [US7] Write failing packaging validation tests for bundled models/assets and total installer/model size <2GB in tests/integration/test_installer_bundle.py
- [X] T080 [P] [US7] Write failing upgrade-preserves-settings test in tests/integration/test_installer_upgrade.py
- [X] T125 [P] [US7] Write failing clean-machine startup SLA test for SC-007 launch <=5s in tests/integration/test_installer_launch_time.py

### Implementation for User Story 7

- [X] T081 [US7] Update PyInstaller spec for Flet assets and local model bundling in ./CVCutter.spec
- [X] T082 [US7] Implement installer build orchestration and artifact checks in ./build_exe.py
- [X] T083 [P] [US7] Add installer smoke-validation script for clean-machine launch-time verification (SC-007: launch <=5s on clean machine) in tools/validate_installer.ps1
- [X] T084 [P] [US7] Add upgrade migration verification path in src/cvcutter/application/migration_service.py

**Checkpoint**: US7 delivers distributable installer with upgrade safety.

---

## Phase 10: User Story 8 - Efficient Resource Usage for Large Videos (Priority: P3)

**Goal**: Ensure streaming/chunked processing keeps memory and disk usage within defined thresholds.

**Independent Test**: Process 4K/2-hour reference input and verify peak memory <4GB and temp disk <=2x source size.

### Tests for User Story 8 (MANDATORY)

- [X] T085 [P] [US8] Write failing performance benchmark tests for memory/disk constraints in tests/integration/test_resource_efficiency.py
- [X] T086 [P] [US8] Write failing unit tests for disk preflight guard and throughput ETA in tests/unit/application/test_pipeline_resources.py
- [X] T126 [P] [US8] Write failing SC-001 processing-speed benchmark test (GPU <60 min, CPU <150 min for 2h 1080p reference) in tests/integration/test_processing_benchmarks.py

### Implementation for User Story 8

- [X] T087 [US8] Implement streaming frame/audio processing paths in src/cvcutter/infrastructure/ffmpeg/transcoder.py
- [X] T088 [P] [US8] Implement disk-space preflight validation before export in src/cvcutter/application/pipeline.py
- [X] T089 [P] [US8] Implement throughput-based ETA calculation in src/cvcutter/application/pipeline.py
- [X] T090 [P] [US8] Add resource telemetry logging hooks for benchmark verification in src/cvcutter/infrastructure/logging/structured_logger.py

**Checkpoint**: US8 achieves bounded-resource processing behavior.

---

## Phase 11: Polish & Cross-Cutting Improvements

**Purpose**: Final hardening across stories before mandatory gates.

- [X] T091 [P] Refine Japanese user-facing copy and error-help text in src/cvcutter/presentation/views/{load_view.py,process_view.py,preview_view.py,upload_view.py,settings_view.py}
- [X] T092 [P] Add regression tests for edge cases (silent input, single performance, corrupt media, dictionary unavailable, segment/program-entry count mismatch with manual resolution) in tests/integration/test_edge_cases.py
- [X] T093 [P] Update operator and developer workflow documentation in README.md and specs/001-codebase-refactor/quickstart.md
- [X] T122 Remove superseded legacy flat modules from src/cvcutter/ root and run_app.py after migration to layered package, then verify no dead imports via pyright(remove only after full migration validation evidence is complete)

---

## Phase 12: Mandatory Pre-Merge Constitution & Quality Gates

**Purpose**: Required evidence and gates before merge/deploy.

- [X] T094 Run full quality gates and capture evidence in docs/qa/001-codebase-refactor-quality-gates.md
- [X] T095 Validate coverage thresholds (>=80% overall, >=90% domain) and record report in test-output/coverage-summary-001-codebase-refactor.md
- [X] T096 Verify module-size policy across src/ and capture output in test-output/module-size-report-001-codebase-refactor.txt
- [X] T097 Validate structured logging and checkpoint resume traceability end-to-end in tests/integration/test_resume_observability.py
- [X] T098 Validate migration/regeneration behavior and user-visible notices in tests/integration/test_migration_regeneration.py
- [X] T099 [P] Run architecture-boundary review and capture findings in docs/reviews/001-architecture-boundary-review.md
- [X] T100 [P] Run correctness/domain-logic review and capture findings in docs/reviews/001-correctness-review.md
- [X] T101 [P] Attach constitution compliance checklist evidence in docs/reviews/001-constitution-compliance.md
- [X] T102 Run quickstart command-path validation and troubleshooting checks in specs/001-codebase-refactor/quickstart.md
- [X] T108 Validate credential security requirements (SC-013: per-user ACL + redaction in logs/UI/diagnostics) in tests/security/test_credentials_security.py
- [X] T109 Validate artifact lifecycle targets (SC-014: cleanup threshold + user retention/purge controls) in tests/integration/test_artifact_lifecycle.py
- [X] T110 Validate full local-only operation with external services disabled in tests/integration/test_local_only_mode.py
- [X] T120 Validate SC-001 processing benchmark thresholds (GPU/CPU timing targets) in tests/integration/test_processing_benchmarks.py
- [X] T123 Execute tools/validate_installer.ps1 on clean-machine profile and record SC-007 launch-time evidence in test-output/installer-launch-sla-001-codebase-refactor.txt (requires T081/T082/T083 completion; terminal gate, not an early provisional run)

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 (Setup): starts immediately.
- Phase 2 (Foundational): depends on Phase 1 completion; blocks all stories.
- Phase 3 (US1 Baseline): depends on Phase 2.
- Phase 4 (US2 Resume): depends on US1 pipeline + Phase 2.
- Phase 5 (US3 Detection Accuracy): depends on US1 baseline pipeline + Phase 2.
- Phase 6 (US4 Mapping): depends on US1 baseline outputs and Phase 2; US3 detection quality enables SC-003 accuracy targets.
- Phase 7 (US5 UI): depends on Phase 2; integrates progressively with US1/US3/US4/US6.
- Phase 8 (US6 Upload): backend tasks depend on US4 mapping outputs; T078 UI wiring depends on US5 upload view-model integration surface.
- Phase 9 (US7 Installer): depends on US5 + US6 production paths.
- Phase 10 (US8 Efficiency): depends on US1 pipeline baseline and US3 detectors.
- Phase 11 (Polish): depends on all desired stories.
- Phase 12 (Mandatory Gates): final sign-off depends on completion of all targeted implementation phases; listed gate tasks may be run provisionally earlier as non-blocking pre-runs only when their prerequisites are satisfied, but merge-authoritative evidence requires terminal re-runs in Phase 12 (artifact-dependent gates such as T123 remain terminal-only).

### User Story Dependency Graph

- US1 → enables US2, US3
- US1 → enables US4 baseline mapping inputs
- US3 → enables US4 quality targets and US8 resource optimization
- US4 → enables US6 backend workflow
- US5 → enables US6 UI wiring (T078)
- US5 + US6 → enable US7 packaging acceptance
- US8 is optimization-hardening on top of US1/US3

### Recommended Delivery Order

1. Baseline foundation: US1
2. Reliability + detection quality: US2 + US3
3. Metadata + UX: US4 + US5
4. Publishing: US6
5. Distribution + scale hardening: US7 + US8
6. Final polish + mandatory gates

### Parallel Opportunities by Story

- **US1**: T021/T022/T023/T127/T104 in parallel; T111 after T021; T024/T025/T026/T112/T121 in parallel before T027; then T028, with T029 in parallel as supporting DTO wiring.
- **US2**: T030/T031/T032/T105/T113 in parallel; T033 and T034 can proceed in parallel before T035; then T036, with T037 and T114 in parallel after T035.
- **US3**: T038/T040 in parallel; T039 before T041/T042/T043; T045/T046 in parallel with T041/T042/T043; then T044; then T047.
- **US4**: T048/T049/T050/T106/T115/T116/T119 in parallel; T051/T052/T053/T054 and T056/T057/T058/T059/T060 in parallel; then T055; then T061.
- **US5**: T062/T063/T064 in parallel; T065/T066/T067 in parallel before T068; then T069.
- **US6**: T070/T071/T072 in parallel; T073/T074/T076 in parallel, then T075 → T077 → T078 (shared workflow/status integration path).
- **US7**: T079/T080/T125 in parallel; T081 and T082 in sequence, T083 in parallel with T084 after packaging updates.
- **US8**: T085/T086/T126 in parallel; T088/T089/T090 can run after T087 baseline changes.

---

## Parallel Example: User Story 4

```bash
# Parallel test-first tasks
Task: "T048 [US4] tests/unit/domain/test_mapping.py"
Task: "T049 [US4] tests/contract/test_mapping_service_contracts.py"
Task: "T050 [US4] tests/integration/test_segment_to_mapping.py"
Task: "T106 [US4] tests/unit/application/test_mapping_workflow.py"
Task: "T115 [US4] tests/integration/test_mapping_benchmarks.py"
Task: "T116 [US4] tests/contract/test_gemini_contract.py"
Task: "T119 [US4] tests/contract/{test_forms_contract.py,test_sheets_contract.py}"

# Parallel implementation batches
Task: "T051 src/cvcutter/domain/mapping/pdf_extraction.py"
Task: "T052 src/cvcutter/domain/mapping/transcription.py"
Task: "T053 src/cvcutter/domain/mapping/form_matching.py"
Task: "T054 src/cvcutter/domain/mapping/music_lookup.py"
Task: "T056 src/cvcutter/infrastructure/pdf/local_extractor.py"
Task: "T057 src/cvcutter/infrastructure/models/whisper_runner.py"
Task: "T058 src/cvcutter/infrastructure/music/sqlite_lookup.py"
Task: "T059 src/cvcutter/infrastructure/{csv/form_csv_loader.py,google/forms_client.py,google/sheets_client.py,forms/form_data_service.py}"
Task: "T060 src/cvcutter/infrastructure/gemini/client.py"

# Then sequential gates
Task: "T055 src/cvcutter/domain/mapping/composite_mapper.py"
Task: "T061 src/cvcutter/application/mapping_workflow.py"
```

## Implementation Strategy

### Baseline First (User Story 1)

1. Complete Phase 1 and Phase 2.
2. Complete US1 (Phase 3) and validate independent test for baseline processing.
3. Run non-gating dry-runs of selected final gates (T094–T097) as provisional baseline diagnostics before expansion; authoritative Phase-12 evidence still requires terminal re-runs after all targeted phases complete.

### Incremental Delivery

1. Add US2 + US3 for reliability and detection-quality baseline.
2. Add US4 + US5 for metadata completeness and operator usability.
3. Add US6 for publication workflow.
4. Add US7 + US8 for distribution and large-input robustness.
5. Finish with Phase 11 and full Phase 12 evidence package.

### Constitution Alignment Notes

- CA-001/CA-009: Enforced by T008, T012–T020, T099, and legacy cleanup task T122.
- CA-002/CA-005/SC-008: Enforced by test-first sequencing across all story phases and T094–T095.
- CA-003/FR-040..FR-047/SC-012: Enforced by T028, T030–T037, T061, T075, T097, T109, T113, and T114.
- CA-004/FR-011/FR-035/FR-036: Enforced by T041–T061 and local-only validation T110.
- CA-006/FR-072: Enforced by T010, T019, T084, T098.
- CA-007/SC-009: Enforced by T005 and T096.
- CA-008: Enforced by T099–T101.
- SC-013/FR-005/FR-006: Enforced by T108.
- SC-014/FR-046: Enforced by T028, T032, T066, T067, and T109.
- FR-050..FR-055: Enforced by T070–T078.
- SC-001/SC-003/SC-004/SC-011: Enforced by T127/T126/T120, T115, T031, and T072.
- SC-002/SC-005/SC-006/SC-007/SC-010: Enforced by T040, T085, T064, T083, T125, T123, and T094.
- CA-010: Enforced by T004, T094, and quickstart validation T102.


