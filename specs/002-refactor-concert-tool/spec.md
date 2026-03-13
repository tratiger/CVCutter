# Feature Specification: CVCutter End-to-End Refactor

**Feature Branch**: `002-refactor-concert-tool`  
**Created**: 2026-03-12  
**Status**: Ready for Planning  
**Input**: User description: "`@refact-plan.md specify` (large-scale refactor plan for concert video splitting, audio synchronization, and automated publishing workflow)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resume-Safe Core Processing (Priority: P1)

As an operator, I can run the core processing workflow (ingest, segmentation, audio sync, metadata mapping, and export-ready outputs) and resume from the last successful step after interruptions.

**Why this priority**: Reliability of the core pipeline is the highest business value because long-running jobs fail in real environments and manual restarts are costly.

**Independent Test**: Start a multi-step job, force interruption after a checkpointed step, restart the application, and verify the same job resumes from the next pending step without duplicating completed outputs.

**Acceptance Scenarios**:

1. **Given** a new job with valid media and metadata inputs, **When** the operator starts processing, **Then** each step completes in order and saves checkpoint status.
2. **Given** a job interrupted after at least one completed step, **When** the operator chooses resume, **Then** the system continues from the last incomplete step and preserves prior results.
3. **Given** a transient external-service failure, **When** retry logic executes, **Then** the step retries safely and either succeeds or returns an actionable recovery prompt.
4. **Given** a processing profile was changed after the latest checkpoint, **When** resume is requested, **Then** the system requires explicit confirmation to invalidate affected downstream checkpoints before continuing.
5. **Given** a completed or failed job, **When** the operator opens run history, **Then** stage transitions, retries, and outcomes are visible in chronological order.
6. **Given** a workstation without optional hardware acceleration, **When** the operator starts processing, **Then** the workflow still runs using the fallback execution path.
7. **Given** any core processing stage begins or ends, **When** diagnostics are reviewed, **Then** structured start/completion/failure events are present for that stage.
8. **Given** a long recording on a memory-constrained workstation, **When** processing runs end-to-end, **Then** the job completes without memory exhaustion failure.
9. **Given** one job is already active on the workstation, **When** the operator attempts to start a second job, **Then** the system blocks the new start request and shows single-active-job guidance.

---

### User Story 2 - Guided Setup and Transparent Progress (Priority: P2)

As an operator with mixed technical skill, I can configure jobs through a guided flow and understand what the system is doing at each stage.

**Why this priority**: Better setup and progress visibility directly reduce setup errors, support requests, and abandoned runs.

**Independent Test**: Have a first-time operator configure and launch a job using only on-screen guidance, then verify stage-level progress and clear error guidance are visible during execution.

**Acceptance Scenarios**:

1. **Given** a first-time operator, **When** they create a new job, **Then** required inputs (including program/song-list metadata) are collected step-by-step with immediate validation feedback.
2. **Given** a running job, **When** the operator opens the progress view, **Then** current stage, completed stages, and pending stages are clearly shown.
3. **Given** a recoverable configuration issue, **When** processing stops, **Then** the operator receives corrective guidance and can continue without recreating the job.
4. **Given** a new job configuration, **When** the operator chooses a performance classification strategy, **Then** the selected strategy is saved and used for that job.
5. **Given** the selected classification strategy returns no confident match, **When** results are presented, **Then** the operator receives a guided prompt to switch strategy or adjust matching inputs.
6. **Given** content-based classification is selected, **When** pre-performance speech is transcribed and matched to the program/song list, **Then** the best match is proposed with confidence and traceable source context.
7. **Given** required local analysis models are missing or unavailable, **When** the operator starts model-dependent processing, **Then** the system either runs with available modalities in reduced-confidence mode (with warning) or blocks execution with actionable remediation guidance when no viable modality remains.
8. **Given** timestamp-based classification is selected and recording-time metadata is available, **When** classification runs, **Then** performances are mapped using recording-time metadata and the resulting confidence is shown for operator review.
9. **Given** timestamp-based classification is selected and recording-time metadata is missing or invalid, **When** classification is requested, **Then** execution is blocked with guidance to correct metadata or switch strategy.

---

### User Story 3 - Accurate Segmenting and Audio Alignment (Priority: P3)

As an editor, I receive high-quality automatic performance segment boundaries and synchronized audio outputs, with operator adjustments when confidence is low.

**Why this priority**: Output quality determines whether the automation is trusted for production use.

**Independent Test**: Process a validation set with known segment boundaries and multi-source audio offsets, then verify proposed boundaries and synchronization quality meet acceptance thresholds with targeted manual review only where confidence is low.

**Acceptance Scenarios**:

1. **Given** a long concert recording, **When** automatic segment detection runs, **Then** the system produces candidate performance intervals with confidence indicators.
2. **Given** multiple audio sources with timing offsets, **When** synchronization runs, **Then** aligned output is produced and per-source tuning controls are available before export.
3. **Given** low-confidence boundary detection, **When** results are presented, **Then** operator confirmation is required before final export.
4. **Given** audio tuning is required, **When** the operator opens tuning controls, **Then** they can switch between simple controls (level/noise sliders) and waveform-preview controls (visual alignment with manual offset adjustment) before export.
5. **Given** the operator changes the low-confidence threshold for a job, **When** detection results are refreshed, **Then** the set of items requiring confirmation follows the updated threshold.
6. **Given** a validation sample with known timing offsets, **When** synchronization completes, **Then** alignment error stays within the defined quality tolerance or the output is flagged for manual correction.
7. **Given** multimodal boundary detection runs, **When** audio applause/silence transitions and visual performance cues disagree, **Then** the system presents confidence-weighted candidates for operator confirmation.

---

### User Story 4 - Stable Automated Publishing (Priority: P4)

As a publisher, I can automatically produce publish-ready media assets and send them to approved external destinations with robust recovery from network instability.

**Why this priority**: Publishing automation is valuable after core processing is reliable and visible.

**Independent Test**: Complete a job with approved metadata and enable publishing; simulate network instability and confirm retries recover without duplicate published items.

**Acceptance Scenarios**:

1. **Given** finalized segments and metadata, **When** the operator starts publishing, **Then** outputs are published in the configured order with expected metadata.
2. **Given** a network interruption during publishing, **When** connectivity returns, **Then** publishing resumes or retries without duplicating already published items.
3. **Given** optional opening title overlay is enabled, **When** export occurs, **Then** each output includes the opening title for the configured duration.
4. **Given** publishing is configured to a non-approved destination, **When** the operator starts publishing, **Then** execution is blocked with a clear policy violation message.

---

### User Story 5 - Install and First Launch (Priority: P5)

As a non-engineering user, I can install the packaged application on a supported workstation and complete first launch without developer setup steps.

**Why this priority**: This unlocks broader adoption after core processing and publishing reliability are in place.

**Independent Test**: On a clean supported workstation, install the packaged application, launch it, and complete initial setup guidance without using developer tooling.

**Acceptance Scenarios**:

1. **Given** a clean supported workstation, **When** installation starts, **Then** the application installs without requiring developer tools.
2. **Given** first launch on a supported workstation, **When** the user opens the application, **Then** onboarding guidance leads to successful creation of a first job draft.
3. **Given** an unsupported workstation environment, **When** installation starts, **Then** the installer blocks gracefully and explains supported environments.

---

### Edge Cases

- Input media duration exceeds standard event length and includes long idle sections before/after performances.
- Audio sources have different sample quality, missing sections, or abrupt clipping at start/end.
- Metadata from forms is partially missing, duplicated, or conflicts with detected performance candidates.
- An interruption occurs during output writing after upstream processing already finished.
- External publishing service accepts the file but delays final completion status callbacks.
- Operator switches processing profiles mid-job and attempts to resume from an older checkpoint.
- Confidence scores cluster near the low-confidence threshold and require predictable operator-review behavior.
- Installation is attempted on an unsupported workstation environment.
- Required local analysis models are missing, corrupted, or incompatible at runtime.
- Timestamp-based classification is selected but recording-time metadata is missing or invalid.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow operators to create and save a job draft that links source media, metadata inputs (including program/song-list metadata), and output preferences.
- **FR-002**: The system MUST validate required job inputs before execution and block execution until critical fields are complete.
- **FR-003**: The system MUST execute processing as named, observable stages with explicit stage-level status.
- **FR-004**: The system MUST persist checkpoint state after each completed stage so interrupted jobs can resume.
- **FR-005**: The system MUST provide an operator-driven resume action that continues from the first incomplete stage.
- **FR-006**: The system MUST prevent duplicate outputs when resumed or retried stages are executed.
- **FR-007**: The system MUST provide clear user-facing error messages that distinguish recoverable issues from blocking failures.
- **FR-008**: The system MUST provide guided setup flow for job configuration, including contextual validation and correction guidance.
- **FR-009**: The system MUST provide live progress visibility including current stage, completed stages, pending stages, and last error summary.
- **FR-010**: The system MUST detect candidate performance boundaries using combined audio-transition and visual-cue evidence when both are available, and MUST fall back to single-modality detection with reduced-confidence labeling when one modality is unavailable.
- **FR-011**: The system MUST provide confidence indicators for detected boundaries and require operator confirmation when confidence is below a defined threshold.
- **FR-012**: The system MUST align multiple audio sources automatically and support switchable tuning modes: simple controls (level/noise sliders) and waveform-preview controls (visual alignment with manual offset adjustment).
- **FR-013**: The system MUST support processing of long recordings without full-video/frame in-memory loading and MUST keep memory-bounded behavior for audio synchronization workloads.
- **FR-014**: The system MUST map validated metadata to each finalized output segment before publishing.
- **FR-015**: The system MUST support optional opening-title insertion per output with operator-controlled enable/disable and configurable display duration.
- **FR-016**: The system MUST restrict external integrations to the feature's approved-service inventory (constitution-approved services plus formally documented CR-005 exceptions) and reject all others by default.
- **FR-017**: The system MUST retry transient external-service failures with safe retry behavior and record retry outcomes.
- **FR-018**: The system MUST retain an auditable execution history for job creation, stage transitions, retries, and completion outcomes.
- **FR-019**: Operators MUST be able to select a classification strategy per job, where content-based classification uses pre-performance speech transcription matched against program/song-list metadata and returns confidence with traceable source context, and timestamp-based classification uses recording-time metadata.
- **FR-020**: The system MUST provide a packaged runtime experience suitable for non-engineering users to install and run on supported workstation environments without manual developer setup.
- **FR-021**: The system MUST detect configuration changes made after checkpoint creation and apply a defined configuration-to-stage dependency map to require explicit checkpoint invalidation or cancellation before resume.
- **FR-022**: The system MUST allow operators to configure the low-confidence boundary-detection threshold per job on a 0-100 scale, with a default threshold of 70.
- **FR-023**: The system MUST continue processing when optional hardware acceleration is unavailable by using a CPU-compatible execution path.
- **FR-024**: The system MUST emit structured run events for start, completion, and failure of each core processing step.
- **FR-025**: The system MUST evaluate per-output synchronization quality against an 80 ms median alignment tolerance and MUST flag outputs that exceed tolerance for manual timing correction.
- **FR-026**: The system MUST provide a fallback action when the selected classification strategy yields no confident match, including operator prompt to switch strategy.
- **FR-027**: The system MUST block installation on unsupported workstation environments and explicitly support Windows 10/11 64-bit environments.
- **FR-028**: The system MUST verify required local analysis models before model-dependent stages, allow reduced-confidence fallback when at least one viable modality remains, and block with remediation guidance when no viable modality remains.
- **FR-029**: The system MUST score classification confidence on a 0-100 scale and treat a result as confident only when the top candidate score is >= 70 and at least 10 points above the next candidate.
  When only one candidate exists, the margin condition is considered satisfied.
- **FR-030**: The system MUST migrate the UI layer from customtkinter to Flet and implement all operator-facing workflows defined in this specification.
- **FR-031**: The system MUST prevent concurrent active-job execution on the same workstation instance and provide user-facing guidance when another job is already running.
- **FR-032**: For transient publishing failures, the retry workflow MUST attempt automated recovery within a 15-minute window per output item, measured from the first transient failure event, before requiring manual intervention.
- **FR-033**: When audio-transition and visual-cue evidence disagree in boundary detection, the system MUST present confidence-weighted modality candidates for operator confirmation.
- **FR-034**: When timestamp-based classification is selected, recording-time metadata MUST be present and valid; otherwise classification MUST be blocked with guidance to correct metadata or switch strategy.

### Functional Requirement Acceptance Criteria

- **FR-001** is accepted when operators can save a job draft with linked inputs and selected options.
- **FR-002** is accepted when any missing critical field prevents execution start.
- **FR-003** is accepted when stage names and status transitions are visible during execution.
- **FR-004** is accepted when each completed stage writes a resumable checkpoint.
- **FR-005** is accepted when resume starts at the first incomplete stage.
- **FR-006** is accepted when retries/resumes do not create duplicate media outputs.
- **FR-007** is accepted when every surfaced error includes a recoverability label and next action.
- **FR-008** is accepted when a first-time operator can complete setup with step-level validation prompts.
- **FR-009** is accepted when progress view shows current, completed, pending, and last-error information.
- **FR-010** is accepted when both evidence sources are used when available, and missing-modality runs are labeled reduced-confidence so FR-011 threshold rules determine confirmation behavior.
- **FR-011** is accepted when below-threshold candidates require explicit operator confirmation.
- **FR-012** is accepted when operators can switch between slider-based tuning and waveform-preview/manual-offset tuning modes.
- **FR-013** is accepted when long recordings complete without full-video/frame in-memory loading and with bounded audio-sync memory usage.
- **FR-014** is accepted when each finalized segment receives validated metadata before publishing.
- **FR-015** is accepted when opening-title insertion can be toggled per output and display duration can be configured.
- **FR-016** is accepted when destinations outside the approved list are rejected before external calls, unless a CR-005 exception is formally documented and added to the feature's approved-service inventory prior to runtime use.
- **FR-017** is accepted when transient failures retry safely and retry outcomes are recorded.
- **FR-018** is accepted when chronological run history includes creation, stage transitions, retries, and outcomes.
- **FR-019** is accepted when selected strategy is persisted per job, content-based mode uses speech-transcription-to-program-list matching with confidence and source-context output, and timestamp mode uses recording-time metadata.
- **FR-020** is accepted when non-engineering users can install and launch without developer tooling steps.
- **FR-021** is accepted when post-checkpoint config changes trigger explicit invalidate-or-cancel decisions based on a documented stage-dependency mapping.
- **FR-022** is accepted when the boundary-confidence threshold is editable on a 0-100 scale and defaults to 70.
- **FR-023** is accepted when jobs run to completion on environments without hardware acceleration.
- **FR-024** is accepted when structured start/completion/failure events are present for each core step.
- **FR-025** is accepted when outputs exceeding 80 ms median alignment tolerance are automatically flagged for manual timing correction before publish.
- **FR-026** is accepted when zero-match classification results trigger a guided strategy-switch prompt.
- **FR-027** is accepted when installation attempts outside Windows 10/11 64-bit are blocked with clear supported-environment guidance.
- **FR-028** is accepted when missing local models trigger reduced-confidence fallback for viable single-modality runs and trigger blocking remediation when no viable modality remains.
- **FR-029** is accepted when classification confidence uses the defined 0-100 scoring rule and no-confident-match conditions follow the fixed-threshold-plus-margin criteria.
  Single-candidate cases are accepted when score >= 70 and the system applies the documented single-candidate margin rule.
- **FR-030** is accepted when the Flet-based UI provides all required setup, progress, review, and publish workflows covered by User Stories 1-5.
- **FR-031** is accepted when attempts to start a second active job on the same workstation are blocked with clear user guidance.
- **FR-032** is accepted when each output item either recovers automatically within 15 minutes of first transient failure or is escalated with explicit manual-intervention guidance.
- **FR-033** is accepted when evidence-disagreement cases surface confidence-weighted modality candidates and require explicit operator confirmation.
- **FR-034** is accepted when missing/invalid recording-time metadata blocks timestamp-based classification and presents corrective or strategy-switch guidance.

### Constitutional Requirements *(mandatory)*

- **CR-001 (Layered Design)**: The feature MUST define boundaries between UI, application orchestration, domain logic, and infrastructure adapters.
- **CR-002 (Stream-First Media)**: For long-media processing, the feature MUST define incremental memory-aware execution, MUST avoid full-file/full-frame memory retention assumptions, and MUST include a fallback path when optional acceleration is unavailable.
- **CR-003 (TDD Evidence)**: The feature MUST define how failing tests are authored before implementation, how regression tests are added for discovered defects, and how manual-judgment test protocols capture approver identity (requesting user or designated domain reviewer, not the implementer), date, procedures, materials, acceptance criteria, and post-execution pass/fail outcomes.
- **CR-004 (Resume & Retry)**: For multi-step workflows and external calls, the feature MUST define resumable checkpoints and safe retry behavior that avoids duplicate side effects.
- **CR-005 (Integration Scope)**: The feature MUST list required external services and justify any addition beyond approved project integrations.
- **CR-006 (Quality Gates)**: Implementation validation MUST include successful `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov` runs.
- **CR-007 (Simplicity)**: The feature MUST favor the simplest design that satisfies current requirements and avoid speculative abstractions.

### Constitutional Verification Plan

- **CR-001 Verification**: Planning artifacts MUST include explicit module-boundary definitions for UI, orchestration, domain, and infrastructure.
- **CR-002 Verification**: Test plan MUST include long-media execution on memory-constrained environments, explicit verification that full-file/full-frame retention is not required, and a no-acceleration fallback run.
- **CR-003 Verification**: Test plan MUST include Red-Green-Refactor evidence plus a manual test artifact containing approver identity (requesting user or designated domain reviewer, not the implementer), date, procedures, materials, acceptance criteria, and post-execution pass/fail outcomes.
- **CR-004 Verification**: Validation MUST include interrupted-run resume tests and duplicate-prevention checks across retries.
- **CR-005 Verification**: Dependency inventory MUST include approved services and rationale for any additional integration request.
  Any Google Sheets usage MUST include CR-005 justification as an extension required for linked Google Forms response retrieval.
- **CR-006 Verification**: Delivery checklist MUST include command outputs for `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov`.
- **CR-007 Verification**: Planning notes MUST justify why selected architecture is the minimum structure needed and identify rejected speculative abstractions.

### Key Entities *(include if feature involves data)*

- **Processing Job**: A user-initiated workflow instance containing inputs, selected options, current state, and final outcomes.
- **Stage Checkpoint**: A persisted record of stage completion, resume cursor, retry count, and last error context.
- **Media Segment Candidate**: A proposed performance interval with start/end boundaries, confidence score, and review status.
- **Audio Source Profile**: Per-source alignment offset, level preference, noise reduction preference, and validation result.
- **Metadata Mapping Record**: The association between finalized segments and human-readable metadata used for export/publishing.
- **Publishing Task**: A tracked outbound delivery action with destination, status lifecycle, retry history, and deduplication token.

## Assumptions

- Operators have permission to use all approved external services required for metadata retrieval, automation, and publishing.
- Typical jobs include one long primary video plus one or more auxiliary audio sources.
- Validation datasets and pilot feedback sessions are available to evaluate segmentation and synchronization quality.
- Existing core capabilities for metadata intake and document generation remain in scope and are refactored for reliability rather than replaced by new business behavior.
- Installable distribution is required for non-engineering users on supported workstation environments (Windows 10/11 64-bit).
- "Low-confidence" boundary review uses a default threshold of 70% unless the operator sets another value.
- Packaged delivery for the migrated UI targets standalone Windows desktop distribution that does not require developer toolchains on end-user machines.

## Dependencies

- **Approved External Services**:
  - YouTube service for publish destination operations.
  - Google Forms service for form-response metadata intake.
  - Configured AI provider service for automated classification tasks.
- **CR-005 Extension**:
  - Google Sheets service for linked form-response spreadsheet retrieval is an explicitly justified extension of approved Google Forms response retrieval workflows.
    Status: Approved for this feature as a CR-005 exception and recorded in this feature's approved-service inventory.
- **Validation Assets**:
  - Historical concert recordings and ground-truth annotations for segmentation and sync quality checks.
- **Local Processing Dependencies**:
  - Local speech-transcription model assets for pre-performance content-based classification.
  - Local visual-cue model assets for performance-boundary detection.
- **Operational Prerequisites**:
  - Workstation environment with sufficient storage for intermediate media outputs and retry-safe run history retention.
  - Supported installation targets are Windows 10/11 64-bit workstations.

## Validation Dataset Definition

- **Synchronization/Segmentation Validation Set**:
  - 20 long-recording runs total.
  - At least 200 performance-segment candidates with ground-truth start/end boundaries.
  - Coverage of mixed camera conditions (stable tripod, handheld motion, and partial performer occlusion).
  - Coverage of multi-source audio setups (minimum 2 sources and maximum 4 sources per run).
- **Classification Validation Set**:
  - At least 200 labeled classification attempts with verified program/song-title ground truth.
  - Includes both high-confidence and ambiguous pre-performance speech samples.
  - Includes single-candidate and multi-candidate matching cases.
- This dataset definition is the reference set for FR-025, SC-002, SC-003, SC-008, and SC-009 measurements.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of interrupted jobs resume from the latest checkpoint and complete without recreating job state, measured over at least 50 interruption-injection runs.
- **SC-002**: In a 20-run long-recording validation set, zero runs fail due to memory exhaustion.
- **SC-003**: At least 85% of automatically proposed performance segments (start/end boundary pair) are accepted without manual boundary edits, measured over at least 200 segment candidates.
- **SC-004**: At least 90% of first-time operators can configure and launch a valid job within 8 minutes, measured across at least 10 participants.
- **SC-005**: At least 98% of transient publishing failures recover automatically within 15 minutes without duplicate published outputs, measured across at least 100 injected transient-failure publish attempts.
- **SC-006**: Pilot operators rate workflow transparency and error guidance at 4.0/5.0 or higher in post-run feedback, measured across at least 10 respondents.
- **SC-007**: At least 90% of first-time non-engineering users can install and open the packaged application in under 10 minutes, measured across at least 10 participants.
- **SC-008**: In the 20-run synchronization validation set, at least 90% of outputs achieve median alignment error <= 80 ms without manual correction, and all remaining outputs are clearly flagged for manual timing correction.
- **SC-009**: At least 90% of automated content-based classification proposals are accepted without manual title correction, measured over at least 200 classification attempts in the validation dataset.
