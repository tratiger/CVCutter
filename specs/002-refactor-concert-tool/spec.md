# Feature Specification: CVCutter End-to-End Refactor

**Feature Branch**: `002-refactor-concert-tool`  
**Created**: 2026-03-12  
**Status**: Ready for Planning  
**Input**: User description: "`@refact-plan.md specify` (large-scale refactor plan for concert video splitting, audio synchronization, and automated publishing workflow)"

## Clarifications

### Session 2026-03-14

- Q: 外部連携認証情報の保存方式は? → A: Option D（簡便性優先で平文設定ファイル保存を許可）
- Q: 外部APIでレート制限（429等）が発生した場合、再試行ポリシーをどれに固定するか? → A: Option A（Retry-After優先、指数バックオフ+ジッター、15分超で手動介入）
- Q: 実行履歴と中間生成物の保持期間をどう定義するか? → A: 手動削除運用。ただし、UI上で簡単に消せるようにする。
- Q: 対応する入力/出力フォーマットの範囲をどこまで固定するか? → A: Option Aに加えてMTSをサポート。
- Q: Processing Job / Stage Checkpoint / Publishing Task の一意性ルールをどれで固定するか? → A: Option A（UUID job_id、不変キー、dedupキー一意）。
- Q: ローカルストレージ容量が不足した場合の動作をどれで固定するか? → A: Option A（<20GB警告、<10GB開始ブロック、<5GB安全一時停止）。
- Q: Processing Job の状態遷移をどこまで固定するか? → A: Option A（通常はrunningから終端へ直接遷移、paused/resumableは中断復旧系で使用）。
- Q: 初期リリースで保証するUI言語対応をどこまで固定するか? → A: Option A（初期は日本語UI正式サポート、文言外部化）。
- Q: 初期リリースで満たすアクセシビリティ基準をどこまで固定するか? → A: Option A（キーボード操作完全対応、フォーカス可視化、WCAG 2.1 AA相当）。
- Q: 外部APIのバージョン互換ポリシーをどれで固定するか? → A: Option A（バージョン固定、互換性チェック、非互換時ブロック）。
- Q: 適用すべきコンプライアンス/規制制約をどれで固定するか? → A: Option A（追加の規制要件なし）。
- Q: この機能で明示的に除外するスコープをどれで固定するか? → A: Windows+macデスクトップを対象、クラウド分散実行とモバイルUIは対象外。
- Q: 同一ジョブ下書きの同時編集競合をどう扱うか? → A: Option C（編集排他ロックで同時編集をブロック）。
- Q: CSV/JSONメタデータのスキーマバージョン管理をどう定義するか? → A: Option A（schema_version必須、直前バージョン互換）。
- Q: 要件衝突時のトレードオフ優先順位をどれで固定するか? → A: Option A（完全性/重複防止 > 復旧可能性 > 操作性 > 性能 > 実装コスト）。
- Q: operator/editor/publisher の役割用語をどう正規化するか? → A: Option C（実ロールはoperator、editor/publisherは文脈ラベル）。
- Q: macOSサポート対象バージョン範囲をどれで固定するか? → A: Option A（macOS 13以上、Apple Silicon/Intel対応）。
- Q: 認証情報の平文保存リスク指摘をどう扱うか? → A: Option C（平文保存を維持し、明示警告と同意を必須化）。
- Q: 統合先のCR-005例外（Google Sheets追加）をどう扱うか? → A: Option A（例外記述を削除し、承認済み統合のみ許可）。
- Q: FR-013 の memory-bounded をどの閾値で定量化するか? → A: Option A（長尺検証でピークRSS 8GB以下）。
- Q: FR-030と受け入れ基準のスコープ不一致をどう解消するか? → A: Option A（ACを全operator workflowトレーサビリティ検証へ拡張）。

## User Scenarios & Testing *(mandatory)*

Role terminology note: Authorization role is `operator`; `editor` and `publisher` labels in stories describe workflow context only.

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
10. **Given** the application was force-closed while a job was active, **When** the operator restarts the application, **Then** the system blocks new-job creation until stale-state detection/transition completes and then presents resumable-state guidance.

---

### User Story 2 - Guided Setup and Transparent Progress (Priority: P2)

As an operator with mixed technical skill, I can configure jobs through a guided flow and understand what the system is doing at each stage.

**Why this priority**: Better setup and progress visibility directly reduce setup errors, support requests, and abandoned runs.

**Independent Test**: Have a first-time operator configure and launch a job using only on-screen guidance, then verify stage-level progress and clear error guidance are visible during execution.

**Acceptance Scenarios**:

1. **Given** a first-time operator, **When** they create a new job, **Then** required baseline inputs are collected step-by-step with immediate validation feedback, and strategy-specific metadata (including event schedule metadata for timestamp mode) is requested when needed.
2. **Given** a running job, **When** the operator opens the progress view, **Then** current stage, completed stages, and pending stages are clearly shown.
3. **Given** a recoverable configuration issue, **When** processing stops, **Then** the operator receives corrective guidance and can continue without recreating the job.
4. **Given** a new job configuration, **When** the operator chooses a performance classification strategy, **Then** the selected strategy is saved and used for that job.
5. **Given** the selected classification strategy returns no confident match, **When** results are presented, **Then** the operator receives guided recovery options to switch strategy and adjust matching inputs.
6. **Given** content-based classification is selected, **When** pre-performance speech is transcribed and matched to the program/song list, **Then** the best match is proposed with confidence and traceable source context.
7. **Given** required local analysis models are missing or unavailable, **When** the operator starts model-dependent processing, **Then** the system either runs with available modalities in reduced-confidence mode (with warning) or blocks execution with actionable remediation guidance when no viable modality remains.
8. **Given** timestamp-based classification is selected and recording-time metadata is available, **When** classification runs, **Then** performances are mapped using recording-time metadata and the resulting confidence is shown for operator review.
9. **Given** timestamp-based classification is selected and recording-time metadata is missing or invalid, **When** classification is requested, **Then** execution is blocked with guidance to correct metadata or switch strategy.
10. **Given** timestamp-based classification is selected but event schedule metadata is unavailable, **When** classification is requested, **Then** execution is blocked with guidance to provide event schedule metadata or switch strategy.

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
8. **Given** only one audio-capable source exists and it is the embedded audio in the video, **When** the synchronization stage is reached, **Then** synchronization is automatically skipped and processing continues.
9. **Given** the video has no usable embedded audio and exactly one external audio source, **When** the synchronization stage is reached, **Then** the system requires user-guided manual synchronization before continuing.

---

### User Story 4 - Stable Automated Publishing (Priority: P4)

As a publisher, I can automatically produce publish-ready media assets and send them to approved external destinations with robust recovery from network instability.

**Why this priority**: Publishing automation is valuable after core processing is reliable and visible.

**Independent Test**: Complete a job with approved metadata and enable publishing; simulate network instability and confirm retries recover without duplicate published items.

**Acceptance Scenarios**:

1. **Given** finalized segments and metadata, **When** the operator starts publishing, **Then** outputs are published in the configured order with expected metadata.
2. **Given** a network interruption during publishing, **When** connectivity returns, **Then** publishing resumes or retries without duplicating already published items and attempts automated recovery per output item within 15 minutes of first transient failure before manual intervention.
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
- External service calls repeatedly return rate-limit responses (HTTP 429), with and without `Retry-After` headers.
- Operator switches processing profiles mid-job and attempts to resume from an older checkpoint.
- Confidence scores cluster near the low-confidence threshold and require predictable operator-review behavior.
- Installation is attempted on an unsupported workstation environment.
- Required local analysis models are missing, corrupted, or incompatible at runtime.
- Timestamp-based classification is selected but recording-time metadata is missing or invalid.
- Timestamp-based classification is selected but event schedule metadata is unavailable, so event-window bounds cannot be derived.
- Application is force-closed while a job is marked active and must be recovered safely on restart.
- Single-source audio jobs where embedded video audio is absent and only one external source is available.
- Manual cleanup is not performed and local storage approaches exhaustion.
- An invalid job-state transition is requested (for example, `completed -> running`).
- External API version drift causes incompatibility with approved integration adapters.
- Concurrent draft-edit attempts target the same job from multiple app instances.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow operators to create and save a job draft that links source media, baseline metadata inputs (including program/song-list metadata), strategy-specific metadata as needed, and output preferences.
- **FR-002**: The system MUST validate required job inputs before execution based on the selected strategy and block execution until critical fields are complete.
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
- **FR-013**: The system MUST support processing of long recordings without full-video/frame in-memory loading and MUST keep peak process RSS at or below `8 GB` for validation-profile synchronization workloads (up to 4 audio sources).
- **FR-014**: The system MUST map validated metadata to each finalized output segment before publishing.
- **FR-015**: The system MUST support optional opening-title insertion per output with operator-controlled enable/disable and configurable display duration.
- **FR-016**: The system MUST restrict external integrations to the feature's constitution-approved service inventory and reject all others by default.
- **FR-017**: The system MUST retry transient external-service failures with safe retry behavior, prioritize `Retry-After` when present, otherwise use exponential backoff with jitter (1s initial delay, 60s max delay), escalate to manual intervention after 15 minutes from first transient failure for that operation, and record retry outcomes.
- **FR-018**: The system MUST retain an auditable execution history for job creation, stage transitions, retries, and completion outcomes.
- **FR-019**: Operators MUST be able to select a classification strategy per job, where content-based classification uses pre-performance speech transcription matched against program/song-list metadata and returns confidence with traceable source context, and timestamp-based classification uses recording-time metadata plus event schedule metadata with derivable event-window bounds.
- **FR-020**: The system MUST provide a packaged runtime experience suitable for non-engineering users to install and run on supported workstation environments without manual developer setup.
- **FR-021**: The system MUST detect configuration changes made after checkpoint creation and apply a defined configuration-to-stage dependency map to require explicit checkpoint invalidation or cancellation before resume.
- **FR-022**: The system MUST allow operators to configure the low-confidence boundary-detection threshold per job on a 0-100 scale, with a default threshold of 70.
- **FR-023**: The system MUST continue processing when optional hardware acceleration is unavailable by using a CPU-compatible execution path.
- **FR-024**: The system MUST emit structured run events for start, completion, and failure of each core processing step.
- **FR-025**: The system MUST evaluate per-output synchronization quality against an 80 ms median alignment tolerance and MUST flag outputs that exceed tolerance for manual timing correction.
- **FR-026**: The system MUST provide a fallback action when the selected classification strategy yields no confident match, including operator guidance to switch strategy and adjust matching inputs.
- **FR-027**: The system MUST block installation on unsupported workstation environments and explicitly support Windows desktop (10/11, 64-bit) and macOS 13+ desktop environments (Apple Silicon and Intel).
- **FR-028**: The system MUST verify required local analysis models before model-dependent stages, allow reduced-confidence fallback when at least one viable modality remains, and block with remediation guidance when no viable modality remains.
- **FR-029**: The system MUST score classification confidence on a 0-100 scale and treat a result as confident only when the top candidate score is >= 70 and at least 10 points above the next candidate.
  When only one candidate exists, the margin condition is considered satisfied.
- **FR-030**: The system MUST migrate the UI layer from customtkinter to Flet and implement all operator-facing workflows defined in this specification.
- **FR-031**: The system MUST enforce workstation-wide single-active-job execution (including cross-process/app-instance starts) and provide user-facing guidance when another job is already running.
- **FR-032**: For transient publishing failures, the retry workflow MUST attempt automated recovery within a 15-minute window per output item, measured from the first transient failure event, before requiring manual intervention.
- **FR-033**: When audio-transition and visual-cue evidence disagree in boundary detection, the system MUST present confidence-weighted modality candidates for operator confirmation.
- **FR-034**: When timestamp-based classification is selected, recording-time metadata MUST be present and valid and event schedule metadata MUST provide derivable event-window bounds; otherwise classification MUST be blocked with guidance to correct metadata or switch strategy.
- **FR-035**: On startup, the system MUST detect stale active-job states with no running process and transition them to resumable state before allowing new-job creation.
- **FR-036**: For single-audio-source jobs, the system MUST auto-skip synchronization when the source is embedded video audio only, and MUST require user-guided manual synchronization when embedded video audio is unavailable and only one external source exists.
- **FR-037**: The system MUST permit external-service credentials to be stored in plaintext local configuration files for simplified single-user workstation setup, and MUST require explicit user acknowledgment of the associated security risk with clear warning text before enabling this mode.
- **FR-038**: The system MUST not auto-delete execution history or intermediate media artifacts, and MUST provide simple UI actions for operators to manually delete these records and files.
- **FR-039**: The system MUST officially support input video containers `MP4`/`MOV`/`MKV`/`MTS`, input audio formats `WAV`/`FLAC`/`AAC`, metadata formats `CSV`/`JSON` (UTF-8), and output media in `MP4` container with `AAC` audio.
- **FR-040**: The system MUST enforce immutable `job_id` (UUID) identity for each processing job, unique checkpoint identity by (`job_id`, `stage_name`, `attempt`), and unique publishing dedup identity by (`job_id`, `segment_id`, `destination`).
- **FR-041**: The system MUST monitor local free storage and apply thresholds: warning below `20 GB`, block new job starts below `10 GB`, and safely pause active jobs below `5 GB` while showing operator cleanup guidance.
- **FR-042**: The system MUST enforce processing-job lifecycle transitions where normal execution allows `running -> completed|failed|canceled`, while interruption recovery uses `running -> paused -> resumable -> running`, and MUST reject invalid transitions with actionable operator guidance.
- **FR-043**: The system MUST provide Japanese-language UI coverage for all operator-facing workflows in this specification, and MUST externalize UI strings to support future multilingual extension.
- **FR-044**: The system MUST support keyboard-only execution of all primary operator workflows, provide visible focus indication on interactive controls, and meet WCAG 2.1 AA-equivalent contrast requirements on primary screens.
- **FR-045**: The system MUST pin supported API versions for each approved external service integration, perform compatibility checks before processing/publishing operations, and block execution with remediation guidance when incompatibility is detected.
- **FR-046**: The feature MUST not introduce additional external regulatory compliance workflows beyond existing project constitutional requirements.
- **FR-047**: The feature scope MUST target desktop application workflows on Windows/macOS only and exclude cloud-distributed execution and mobile UI workflows.
- **FR-048**: The system MUST apply an exclusive edit lock for each job draft and block concurrent edit attempts from other app instances with user-facing lock guidance.
- **FR-049**: The system MUST require `schema_version` in imported metadata payloads, apply explicit compatibility mapping for older versions, and support at least the immediately previous metadata schema version.
- **FR-050**: The system MUST use a single executable authorization role (`operator`) for workflows in this feature, while allowing `editor` and `publisher` labels as scenario-context descriptors only.

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
- **FR-013** is accepted when long recordings complete without full-video/frame in-memory loading and measured peak process RSS remains <= `8 GB` for validation-profile synchronization workloads (up to 4 audio sources).
- **FR-014** is accepted when each finalized segment receives validated metadata before publishing.
- **FR-015** is accepted when opening-title insertion can be toggled per output and display duration can be configured.
- **FR-016** is accepted when destinations outside the constitution-approved service inventory are rejected before external calls.
- **FR-017** is accepted when transient failures (including HTTP 429 rate limiting) retry safely using `Retry-After` when available or exponential backoff with jitter otherwise, operations exceeding 15 minutes from first transient failure are escalated to manual intervention, and retry outcomes are recorded.
- **FR-018** is accepted when chronological run history includes creation, stage transitions, retries, and outcomes.
- **FR-019** is accepted when selected strategy is persisted per job, content-based mode uses speech-transcription-to-program-list matching with confidence and source-context output, and timestamp mode uses recording-time metadata plus event schedule metadata with derivable event-window bounds.
- **FR-020** is accepted when non-engineering users can install and launch without developer tooling steps.
- **FR-021** is accepted when post-checkpoint config changes trigger explicit invalidate-or-cancel decisions based on a documented stage-dependency mapping.
- **FR-022** is accepted when the boundary-confidence threshold is editable on a 0-100 scale and defaults to 70.
- **FR-023** is accepted when jobs run to completion on environments without hardware acceleration.
- **FR-024** is accepted when structured start/completion/failure events are present for each core step.
- **FR-025** is accepted when outputs exceeding 80 ms median alignment tolerance are automatically flagged for manual timing correction before publish.
- **FR-026** is accepted when no-confident-match results trigger guided recovery options that include strategy switch and matching-input adjustment.
- **FR-027** is accepted when installation attempts outside supported Windows 10/11 64-bit or macOS 13+ (Apple Silicon/Intel) environments are blocked with clear supported-environment guidance.
- **FR-028** is accepted when missing local models trigger reduced-confidence fallback for viable single-modality runs and trigger blocking remediation when no viable modality remains.
- **FR-029** is accepted when classification confidence uses the defined 0-100 scoring rule and no-confident-match conditions follow the fixed-threshold-plus-margin criteria.
  Single-candidate cases are accepted when score >= 70 and the system applies the documented single-candidate margin rule.
- **FR-030** is accepted when a workflow traceability matrix demonstrates that every operator-facing workflow required by this specification is implemented in the Flet UI (including setup, progress, review, publish, lock/error guidance, and recovery flows).
- **FR-031** is accepted when attempts to start a second active job from the same workstation (including separate app instances/processes) are blocked with clear user guidance.
- **FR-032** is accepted when each output item either recovers automatically within 15 minutes of first transient failure or is escalated with explicit manual-intervention guidance.
- **FR-033** is accepted when evidence-disagreement cases surface confidence-weighted modality candidates and require explicit operator confirmation.
- **FR-034** is accepted when missing/invalid recording-time metadata, out-of-window timestamps, or unavailable event-window bounds (per event capture window rules) block timestamp-based classification and present corrective or strategy-switch guidance.
- **FR-035** is accepted when restart after forced shutdown converts stale active jobs to resumable state, presents resume guidance, and blocks new-job creation until stale-state detection/transition completes.
- **FR-036** is accepted when single-source embedded-video-audio jobs skip synchronization automatically, while single-source external-audio-only jobs require explicit user-guided manual synchronization.
- **FR-037** is accepted when operator-entered external-service credentials are written to and read from a plaintext local configuration file without additional encryption or OS credential-store usage, and enabling this mode requires explicit user acknowledgment after a clear risk warning.
- **FR-038** is accepted when execution history and intermediate artifacts remain until operator deletion, and operators can remove selected items through direct UI actions without command-line or file-system manual steps.
- **FR-039** is accepted when test jobs using each supported input format (`MP4`/`MOV`/`MKV`/`MTS`, `WAV`/`FLAC`/`AAC`, `CSV`/`JSON`) are ingested successfully and exported outputs are generated as `MP4` with `AAC` audio.
- **FR-040** is accepted when duplicate checkpoint records for the same (`job_id`, `stage_name`, `attempt`) are rejected and duplicate publish attempts for the same (`job_id`, `segment_id`, `destination`) are blocked by dedup identity rules.
- **FR-041** is accepted when capacity monitoring triggers warning (`<20 GB`), start blocking (`<10 GB`), and safe pause (`<5 GB`) behavior with explicit cleanup guidance and resumable-state preservation.
- **FR-042** is accepted when valid direct terminal transitions from `running` succeed, recovery transitions through `paused/resumable` succeed for interrupted runs, invalid transitions are blocked, and blocked attempts include guidance for the nearest valid next state.
- **FR-043** is accepted when all setup/progress/review/publish flows are fully usable in Japanese UI text and string resources are not hard-coded in workflow logic.
- **FR-044** is accepted when primary setup/progress/review/publish workflows are fully operable by keyboard only, focus is visibly trackable on each actionable UI component, and contrast checks pass for defined primary screens.
- **FR-045** is accepted when approved-service inventory includes pinned API versions, compatibility checks run before integration-dependent operations, and incompatible-version cases are blocked with explicit update/remediation guidance.
- **FR-046** is accepted when delivery artifacts define no new external regulatory process gates and rely on existing constitutional controls only.
- **FR-047** is accepted when feature tasks and validation artifacts contain no cloud-distributed execution flow and no mobile UI delivery scope.
- **FR-048** is accepted when concurrent edit attempts on the same job draft are blocked while the lock owner is active, and blocked users receive clear lock-owner and retry guidance.
- **FR-049** is accepted when metadata imports without `schema_version` are rejected with guidance, and imports using the immediately previous schema version are accepted through documented compatibility mapping.
- **FR-050** is accepted when no distinct permission model is required for `editor` or `publisher` tasks and all such flows are executable under the `operator` role.

### Constitutional Requirements *(mandatory)*

- **CR-001 (Layered Design)**: The feature MUST define boundaries between UI, application orchestration, domain logic, and infrastructure adapters.
- **CR-002 (Stream-First Media)**: For long-media processing, the feature MUST define incremental memory-aware execution, MUST avoid full-file/full-frame memory retention assumptions, and MUST include a fallback path when optional acceleration is unavailable.
- **CR-003 (TDD Evidence)**: The feature MUST define how failing tests are authored before implementation, how regression tests are added for discovered defects, and how manual-judgment test protocols capture approver identity (requesting user or designated domain reviewer, not the implementer), date, procedures, materials, acceptance criteria, and post-execution pass/fail outcomes.
- **CR-004 (Resume & Retry)**: For multi-step workflows and external calls, the feature MUST define resumable checkpoints and safe retry behavior that avoids duplicate side effects.
- **CR-005 (Integration Scope)**: The feature MUST list required external services and justify any addition beyond approved project integrations.
- **CR-006 (Quality Gates)**: Implementation validation MUST include successful `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov` runs.
- **CR-007 (Simplicity)**: The feature MUST favor the simplest design that satisfies current requirements and avoid speculative abstractions.
- **CR-008 (Observability)**: Core processing stages MUST emit structured events for start, completion, and failure paths with stage and job context.
- **CR-009 (Tradeoff Priority)**: When requirements conflict, decision priority MUST be `data integrity & deduplication` > `recoverability` > `operator usability` > `performance optimization` > `implementation cost`.

### Constitutional Verification Plan

- **CR-001 Verification**: Planning artifacts MUST include explicit module-boundary definitions for UI, orchestration, domain, and infrastructure.
- **CR-002 Verification**: Test plan MUST include long-media execution on memory-constrained environments, explicit verification that full-file/full-frame retention is not required, and a no-acceleration fallback run.
- **CR-003 Verification**: Test plan MUST include Red-Green-Refactor evidence plus a manual test artifact containing approver identity (requesting user or designated domain reviewer, not the implementer), date, procedures, materials, acceptance criteria, and post-execution pass/fail outcomes.
- **CR-004 Verification**: Validation MUST include interrupted-run resume tests and duplicate-prevention checks across retries.
- **CR-005 Verification**: Dependency inventory MUST include approved services and rationale for any additional integration request.
- **CR-006 Verification**: Delivery checklist MUST include command outputs for `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov`.
- **CR-007 Verification**: Planning notes MUST justify why selected architecture is the minimum structure needed and identify rejected speculative abstractions.
- **CR-008 Verification**: Test plan MUST verify structured event emission for start/completion/failure across each core processing stage.
- **CR-009 Verification**: Design decisions that involve tradeoffs MUST reference the priority order and explain why higher-priority criteria are preserved.

### Key Entities *(include if feature involves data)*

- **Processing Job**: A user-initiated workflow instance containing inputs (including event schedule metadata), selected options, current state, and final outcomes, identified by immutable `job_id` (UUID), with lifecycle states `draft`, `ready`, `running`, `paused`, `resumable`, `failed`, `completed`, and `canceled`.
- **Operator Role**: The single authorization role for this feature's executable workflows; `editor` and `publisher` are context labels used in scenario narratives.
- **Stage Checkpoint**: A persisted record of stage completion, resume cursor, retry count, and last error context, uniquely identified by (`job_id`, `stage_name`, `attempt`).
- **Media Segment Candidate**: A proposed performance interval with start/end boundaries, confidence score, and review status.
- **Audio Source Profile**: Per-source alignment offset, level preference, noise reduction preference, and validation result.
- **Metadata Mapping Record**: The association between finalized segments and human-readable metadata used for export/publishing.
- **Publishing Task**: A tracked outbound delivery action with destination, status lifecycle, retry history, and deduplication token, uniquely keyed by (`job_id`, `segment_id`, `destination`).

## Assumptions

- Operators have permission to use all approved external services required for metadata retrieval, automation, and publishing.
- Typical jobs include one long primary video plus one or more auxiliary audio sources.
- Validation datasets and pilot feedback sessions are available to evaluate segmentation and synchronization quality.
- Existing core capabilities for metadata intake and document generation remain in scope and are refactored for reliability rather than replaced by new business behavior.
- Installable distribution is required for non-engineering users on supported workstation environments (Windows 10/11 64-bit and macOS 13+ on Apple Silicon/Intel).
- "Low-confidence" boundary review uses a default threshold of 70 on a 0-100 scale unless the operator sets another value.
- Packaged delivery for the migrated UI targets standalone desktop distribution for supported Windows and macOS environments without requiring developer toolchains on end-user machines.
- Operators are responsible for manual cleanup of execution history and intermediate media artifacts using built-in UI deletion actions.
- Initial release targets Japanese-speaking operators; UI text is managed as externalized resources to enable future localization.
- No additional external legal/regulatory compliance constraints are imposed for this feature beyond baseline project constitutional controls.
- Cloud-distributed execution and mobile UI delivery are explicitly out of scope for this feature.
- Tradeoff decisions follow this fixed priority: data integrity/deduplication, recoverability, operator usability, performance optimization, then implementation cost.

## Dependencies

- **Approved External Services**:
  - YouTube service for publish destination operations.
  - Google Forms service for form-response metadata intake.
  - Configured AI provider service for automated classification tasks.
  - Each approved service integration records a pinned supported API version in the feature's approved-service inventory.
- **Validation Assets**:
  - Historical concert recordings and ground-truth annotations for segmentation and sync quality checks.
- **Local Processing Dependencies**:
  - Local speech-transcription model assets for pre-performance content-based classification.
  - Local visual-cue model assets for performance-boundary detection.
  - Media processing stack configured to ingest `MP4`/`MOV`/`MKV`/`MTS` video, `WAV`/`FLAC`/`AAC` audio, and `CSV`/`JSON` (UTF-8) metadata.
- **Operational Prerequisites**:
  - Workstation environment with sufficient storage for intermediate media outputs and retry-safe run history retention.
  - Supported installation targets are Windows 10/11 64-bit and macOS 13+ desktop workstations (Apple Silicon/Intel).
  - External-service credentials are managed in plaintext local configuration files on the workstation only after user acknowledgment of displayed security-risk warnings.

## Data and Metric Definitions

- **Recording-Time Metadata Validity Rules**:
  - Required fields: source capture timestamp and source identifier.
  - Accepted timestamp format: ISO 8601 with timezone information.
  - Invalid if timestamp is missing, unparsable, or outside the event capture window for the current job.
  - FR-034 uses these rules to block timestamp-based classification when validity checks fail.
  - **Event capture window rules**:
    - Bounds are derived from job event schedule metadata (event start/end) normalized to the job timezone.
    - Timestamps within the bounds, including a +/- 10 minute tolerance, are valid.
    - If event window bounds are unavailable, timestamp-based classification is blocked and FR-034 guidance is shown.
- **Alignment Error Measurement Rules**:
  - Per output, alignment error is calculated as absolute offset against the designated reference audio source across sampled analysis windows.
  - Median alignment error is the median of sampled-window offsets for that output.
  - FR-025 and SC-008 use this metric definition for pass/fail evaluation.
- **Storage Capacity Threshold Rules**:
  - `<20 GB` free: warning state.
  - `<10 GB` free: block new job starts.
  - `<5 GB` free: safely pause active jobs and require cleanup before resume.
  - FR-041 uses these thresholds for runtime storage-safety behavior.
- **Metadata Schema Version Rules**:
  - Imported CSV/JSON metadata must include `schema_version`.
  - Current schema version and previous schema version are both accepted.
  - Previous-version payloads must be transformed through documented compatibility mappings before validation.
  - FR-049 uses these rules for import compatibility behavior.
- **Memory Bound Measurement Rules**:
  - Peak memory is measured as process RSS maximum during the synchronization stage.
  - Validation profile covers long recordings with up to 4 audio sources.
  - FR-013 and SC-002 use `peak RSS <= 8 GB` as pass/fail threshold.

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
- **SC-002**: In a 20-run long-recording validation set, zero runs fail due to memory exhaustion and each run keeps synchronization-stage peak process RSS <= `8 GB`.
- **SC-003**: At least 85% of automatically proposed performance segments (start/end boundary pair) are accepted without manual boundary edits, measured over at least 200 segment candidates.
- **SC-004**: At least 90% of first-time operators can configure and launch a valid job within 8 minutes, measured across at least 10 participants.
- **SC-005**: At least 98% of transient publishing failures recover automatically within 15 minutes per output item without duplicate published outputs, measured across at least 100 injected transient-failure publish attempts.
- **SC-006**: Pilot operators rate workflow transparency and error guidance at 4.0/5.0 or higher in post-run feedback, measured across at least 10 respondents.
- **SC-007**: At least 90% of first-time non-engineering users can install and open the packaged application in under 10 minutes, measured across at least 10 participants.
- **SC-008**: In the 20-run synchronization validation set, at least 90% of outputs achieve median alignment error <= 80 ms without manual correction, and all remaining outputs are clearly flagged for manual timing correction.
- **SC-009**: At least 90% of automated content-based classification proposals are accepted without manual title correction, measured over at least 200 classification attempts in the validation dataset.
- **SC-010**: In accessibility validation across at least 5 representative operators, 100% of primary workflows complete via keyboard-only operation and all designated primary screens pass WCAG 2.1 AA-equivalent contrast checks.
