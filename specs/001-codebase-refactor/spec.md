# Feature Specification: CVCutter Full Architecture Refactor

**Feature Branch**: `001-codebase-refactor`
**Created**: 2026-03-01
**Status**: Draft
**Input**: User description: "Large-scale CVCutter refactor: architecture separation (MVC/MVVM), modern UI (evaluate flet migration from customtkinter), installer packaging, performance/memory optimization, resume capability, improved video-to-performance mapping via speech transcription and music-information lookup, improved performance-segment detection using multimodal/local methods without external APIs. Maintain identity as integrated concert video splitting, audio synchronization, and YouTube upload orchestration tool."

## Assumptions

- **Target platform**: Windows desktop (primary), with architecture that does not preclude future cross-platform support.
- **User base**: Small team or solo operator managing concert recordings; typically processes 1–20 video files per concert event.
- **Video sources**: Consumer-grade cameras (1080p–4K), single or multi-file recordings of full concerts, with optional external microphone audio.
- **Language**: UI and user-facing text remain Japanese (matching current user base); internal code comments and documentation in English.
- **GPU acceleration**: NVIDIA GPU with NVENC is the primary hardware-acceleration target; the system gracefully degrades to CPU-only processing.
- **Installer target**: Windows installer (e.g., MSI or NSIS-based) distributable as a single downloadable artifact with all required local models bundled; no app-store distribution required.
- **Concert format**: A typical concert has an MC (master of ceremonies) who announces each piece before performers take the stage; performances are separated by applause, stage transitions, and MC announcements.
- **Model size constraints**: Any locally-run models for detection or transcription must be small enough to bundle inside the single installer artifact (target: under 2 GB total model weight). The transcription model is Whisper small (~460 MB); the visual detection model is YOLOv8n (~6 MB); audio content classification uses a lightweight pre-trained local model for music/speech/applause classification (target: <=50 MB).
- **YouTube API quotas**: The existing daily quota constraints (approximately 6 uploads/day) remain; the system must work within these limits.
- **Backward compatibility**: API/UI backward compatibility is not required per constitution. Data/settings continuity is still required through automatic migration of existing configuration and upload-state artifacts; legacy checkpoint files are regenerated under the new format.
- **External API usage for detection**: Performance-segment detection must be fully local; Gemini or similar cloud AI may still be used optionally for metadata enrichment (PDF parsing, form-to-video matching) but must be failure-aware and manually overridable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Process Concert Video End-to-End (Priority: P1)

As a concert video operator, I want to load one or more raw concert video files (and optionally external microphone audio), have the system automatically detect individual performance segments, synchronize high-quality audio, and export each performance as a separate video file — so that I can produce upload-ready clips without manual frame-by-frame editing.

**Why this priority**: This is the core value proposition of CVCutter. Without reliable video processing, no other feature matters.

**Independent Test**: Can be fully tested by providing a sample concert video containing at least 3 performances with audible MC announcements between them, running the processing pipeline, and verifying that 3 correctly-bounded output files are produced with synchronized audio.

**Acceptance Scenarios**:

1. **Given** a single 2-hour concert video file and a corresponding external microphone recording, **When** the user initiates processing, **Then** the system detects all performance segments, synchronizes audio, and exports each segment as a separate file in the configured output directory.
2. **Given** a concert recorded across multiple video files (e.g., 3 files due to camera memory limits), **When** the user loads all files in order, **Then** the system concatenates them logically and detects performances across file boundaries without missing or duplicating segments.
3. **Given** a concert video without an external microphone recording, **When** the user initiates processing with mic audio omitted, **Then** the system processes using the video's embedded audio only, with no errors.
4. **Given** a video where GPU acceleration is available, **When** the user processes with GPU enabled, **Then** encoding completes faster than CPU-only mode with equivalent output quality.

---

### User Story 2 — Resume Interrupted Processing (Priority: P1)

As a concert video operator, I want long-running processing jobs to save progress at meaningful checkpoints — so that if the application crashes, loses power, or I intentionally pause work, I can resume from where it left off rather than restarting from scratch.

**Why this priority**: Concert video processing can take hours. Losing all progress to a crash or power outage is the single most frustrating failure mode.

**Independent Test**: Can be tested by starting a multi-performance processing job, forcibly terminating the application after 2 segments are exported, restarting, and verifying that processing resumes from segment 3.

**Acceptance Scenarios**:

1. **Given** a processing job that has completed 5 of 12 segments, **When** the application is closed and reopened, **Then** the user is offered the option to resume and processing continues from segment 6.
2. **Given** a resumed job where the source video file has been modified since the last checkpoint, **When** the user attempts to resume, **Then** the system detects the input change, warns the user, and offers to restart from the beginning.
3. **Given** a resumed job where configuration (e.g., audio balance, output format) has changed, **When** the user resumes, **Then** the system invalidates affected checkpoints and reprocesses only the segments impacted by the configuration change.

---

### User Story 3 — Accurate Performance Segment Detection (Priority: P1)

As a concert video operator, I want the system to accurately identify the start and end of each musical performance — including distinguishing performance from applause, MC announcements, and stage transitions — so that exported clips contain complete performances without extraneous material.

**Why this priority**: Detection accuracy directly determines output quality. Inaccurate boundaries mean manual re-editing, which defeats the tool's purpose.

**Independent Test**: Can be tested by processing a reference concert video with known performance timestamps and evaluating both recall and boundary accuracy against ground truth for full visual-audio mode and audio-only fallback mode.

**Acceptance Scenarios**:

1. **Given** a concert video with 10 performances separated by MC announcements and applause, **When** detection runs, **Then** at least 9 of 10 performances are detected with start/end boundaries within 5 seconds of the actual performance start/end.
2. **Given** a performance that begins with a quiet solo introduction (low motion, low volume), **When** detection runs, **Then** the segment start is not delayed past the actual musical start by more than 5 seconds.
3. **Given** an extended applause break (>60 seconds) between performances, **When** detection runs, **Then** the applause is not included in either the preceding or following performance segment.
4. **Given** a performance with mid-piece pauses (e.g., between movements of a multi-movement work), **When** detection runs, **Then** the system does not split the performance into multiple segments.
5. **Given** YOLO visual analysis is disabled for low-spec mode, **When** detection runs on the reference set, **Then** the system detects at least 8 of 10 performances and maintains at least 80% boundary accuracy within ±8 seconds.

---

### User Story 4 — Map Videos to Performance Metadata (Priority: P2)

As a concert video operator, I want the system to automatically match each exported video segment to its corresponding performance metadata (piece title, composer, performers) — using MC speech transcription, program PDF parsing, and optionally music-information retrieval — so that YouTube uploads have correct titles and descriptions without tedious manual data entry.

**Why this priority**: Correct metadata is essential for meaningful YouTube uploads, but the mapping can be corrected manually if automation fails. Detection (P1) must work first.

**Independent Test**: Can be tested by providing a concert video with MC announcements, a program PDF, and optionally a Google Form response file, then verifying that at least 80% of segments are matched to the correct metadata.

**Acceptance Scenarios**:

1. **Given** a concert video where the MC announces each piece title before the performance, **When** mapping runs with transcription enabled, **Then** at least 80% of segments are correctly matched to their program entries by title.
2. **Given** a program PDF listing 12 performances, **When** the PDF is parsed and mapped against 12 detected segments, **Then** the sequential order mapping correctly matches at least 90% of performances.
3. **Given** a mapping result with 2 uncertain matches, **When** the user opens the preview/mapping screen, **Then** uncertain matches are visually highlighted and the user can correct them with drag-and-drop or dropdown selection.
4. **Given** that the MC does not announce a piece (skips an announcement), **When** mapping runs, **Then** the system marks that segment as "unmatched" rather than assigning incorrect metadata.
5. **Given** low-confidence transcription results and a local music-information dataset, **When** mapping runs with lookup enabled, **Then** lookup signals are applied to improve match confidence while preserving manual correction controls.
6. **Given** cloud matching is unavailable, **When** form responses are integrated, **Then** the system applies deterministic weighted matching on normalized performer name and piece title, resolves ties by program order, and flags unresolved items for manual review.

---

### User Story 5 — Modern, Responsive User Interface (Priority: P2)

As a concert video operator, I want a clean, modern interface that clearly guides me through each workflow step (load → process → preview/map → upload → settings) — with real-time progress feedback and no frozen windows during long operations.

**Why this priority**: The current UI (customtkinter) mixes business logic with presentation, freezes during processing, and has usability rough edges. A modern UI improves trust and reduces errors, but the core pipeline must work first.

**Independent Test**: Can be tested by walking through the complete workflow (load files → process → preview → upload) and verifying that the UI remains responsive at every step, progress is visible, and all actions are accessible.

**Acceptance Scenarios**:

1. **Given** the user launches the application, **When** the main window appears, **Then** the interface loads within 3 seconds and displays the workflow steps clearly.
2. **Given** a long-running video processing job, **When** encoding is in progress, **Then** a progress indicator shows percentage complete, estimated time remaining, and current operation — and the UI remains interactive (user can navigate other tabs, adjust settings).
3. **Given** an error during processing (e.g., corrupt video file), **When** the error occurs, **Then** a user-friendly error message is displayed with actionable guidance, and the application does not crash.
4. **Given** the user is on the preview/mapping screen, **When** they click on a video segment, **Then** a thumbnail preview and metadata summary appear within 1 second.

---

### User Story 6 — YouTube Upload with Quota Management (Priority: P2)

As a concert video operator, I want to upload processed and mapped videos to YouTube — with automatic title/description/privacy from metadata, playlist assignment, and intelligent quota management — so that I can publish a full concert's worth of videos without manually managing API limits.

**Why this priority**: Upload is the final delivery step. It's valuable but depends on processing and mapping being correct first.

**Independent Test**: Can be tested by preparing 3 processed videos with metadata and initiating upload, verifying that all 3 are uploaded with correct metadata and added to the specified playlist, while respecting quota limits.

**Acceptance Scenarios**:

1. **Given** 8 processed videos with complete metadata and a daily quota allowing 6 uploads, **When** the user starts batch upload, **Then** the first 6 are uploaded, and the remaining 2 are queued for the next quota reset with a clear status message.
2. **Given** an upload that fails mid-transfer due to a network error, **When** the upload is retried, **Then** it resumes from where it left off (resumable upload) rather than restarting.
3. **Given** form responses indicating a performer wants their video set to "unlisted", **When** that video is uploaded, **Then** its privacy setting is correctly set to "unlisted".
4. **Given** completed uploads, **When** the user views the upload status screen, **Then** each video shows its YouTube URL, upload status, and any errors encountered.
5. **Given** uploads are queued due to daily quota exhaustion, **When** Pacific Time reaches 00:00, **Then** queued uploads resume automatically without requiring metadata remapping.

---

### User Story 7 — Install and Run as Desktop Application (Priority: P3)

As a non-technical user, I want to install CVCutter via a standard Windows installer and launch it from the Start Menu — without needing to install Python, manage dependencies, or use the command line.

**Why this priority**: Installer packaging widens the user base but is a distribution concern, not a core capability. The application must function correctly before packaging matters.

**Independent Test**: Can be tested by running the installer on a clean Windows machine (no Python installed), launching the application, and completing a basic video processing task.

**Acceptance Scenarios**:

1. **Given** a clean Windows 10/11 machine with no Python installed, **When** the user runs the installer, **Then** the application installs without errors and appears in the Start Menu within 2 minutes.
2. **Given** an installed application, **When** the user launches it, **Then** the main window appears within 5 seconds.
3. **Given** an installed application with bundled models, **When** the user processes a video, **Then** all local models (detection, transcription) function without requiring additional downloads.
4. **Given** a new version is available, **When** the user runs the new installer, **Then** it cleanly upgrades the existing installation, preserving user settings.

---

### User Story 8 — Efficient Resource Usage for Large Videos (Priority: P3)

As a concert video operator working with 4K multi-hour recordings, I want the system to process videos without exhausting system memory or requiring excessive disk space — so that I can process on a standard workstation (16 GB RAM, 500 GB free disk).

**Why this priority**: Performance and memory efficiency matter for real-world use but are optimization concerns that should follow correct functionality.

**Independent Test**: Can be tested by processing a 4K 2-hour video and monitoring peak memory usage (must stay below 4 GB resident) and temporary disk usage (must not exceed 2× source file size).

**Acceptance Scenarios**:

1. **Given** a 4K 2-hour concert video (approximately 30 GB), **When** processing completes, **Then** peak memory usage does not exceed 4 GB and temporary disk usage does not exceed 60 GB.
2. **Given** processing with GPU acceleration enabled, **When** compared to CPU-only processing of the same video, **Then** total processing time is reduced by at least 40%.
3. **Given** a low-memory system (8 GB RAM), **When** the user processes a 1080p concert video, **Then** the system completes processing without out-of-memory errors, even if slower.

---

### Edge Cases

- **Empty or silent video**: What happens when a video contains no detectable performances (e.g., accidental recording of an empty stage)? The system must report "no performances detected" rather than crash or produce empty files.
- **Single continuous performance**: What happens when the entire concert is one uninterrupted piece with no MC breaks? The system should detect it as a single segment and allow the user to manually split if desired.
- **Corrupted video file**: How does the system handle a video file that is truncated or has codec errors? Processing must fail gracefully with a clear error message identifying the problematic file and timestamp.
- **Mismatched file counts**: What happens when the number of detected segments does not match the number of entries in the program PDF? The mapping screen must clearly show the mismatch and allow manual resolution.
- **Extremely long concerts**: How does the system handle a 5+ hour recording? The checkpoint/resume system must support this, and memory usage must remain bounded.
- **No external audio provided**: The system must process using embedded video audio only, without error or degraded detection accuracy beyond the inherent quality difference.
- **Multiple cameras (future consideration)**: The current spec covers single-camera-angle workflows; multi-angle is out of scope but the architecture should not preclude it.
- **Non-Japanese MC announcements**: Transcription should work for Japanese speech; other languages are out of scope but should not cause crashes (the system may report low-confidence matches).
- **Bundled music dictionary unavailable/corrupted**: Mapping must continue using sequential order, transcription signals, and manual correction without crashing or blocking workflow.
- **Quota exhaustion mid-batch**: If YouTube quota is exhausted partway through a batch, the system must save upload state and allow seamless resumption after quota reset.
- **Quota reset while app is closed**: Queued uploads must be restored and auto-resumed on next launch without forcing remapping.
- **Network loss during upload**: The system must use resumable uploads and retry with exponential backoff; after persistent failure (e.g., 5 retries), it must pause that upload and continue with remaining items.
- **Disk full during export**: The system must detect insufficient disk space before starting export and warn the user, rather than failing mid-write with corrupt output files.

## Clarifications

### Session 2026-03-01

- Q: How should checkpoint and resume state be persisted? → A: Plain-text JSON files in the app config directory (current approach).
- Q: How should API credentials (YouTube OAuth tokens, Google API keys, Gemini keys) be stored? → A: Plain-text JSON files in the application's config directory as the default policy for trusted single-user environments.
- Q: Which UI framework should be used for the modern UI rebuild? → A: Migrate to Flet (replacing customtkinter).
- Q: Which speech transcription model should be used for MC announcement recognition? → A: Whisper small (~460 MB), balancing accuracy for Japanese speech and installer bundle size.
- Q: How should existing configuration files be handled during the refactor migration? → A: Auto-migrate on first launch of the new version (no manual regeneration required).
- Q: What detection strategy should be used for performance-segment identification? → A: Full visual-audio fusion (YOLO visual + audio energy + content classification), with the YOLO visual signal user-configurable to disable for low-spec PCs.
- Q: How should installer artifacts be distributed with local models? → A: Use one downloadable installer artifact that bundles all required local models (no separate companion package and no network fetch during install/first run).
- Q: Should optional secure-store mode for API credentials be implemented in this refactor? → A: No. For this refactor scope, credential handling remains local plain-text JSON with per-user ACL restriction and secret redaction controls.
- Q: How should music-information lookup be concretely implemented? → A: Use a bundled local music-metadata dictionary (title/composer/performer), curated by the development side from internet sources before release; no user runtime network fetch is allowed.
- Q: How should detection accuracy targets apply when YOLO visual analysis is disabled? → A: Use dual targets with both metrics: full visual-audio mode requires recall ≥90% and boundary accuracy ≥90% (±5 seconds), while audio-only fallback mode requires recall ≥80% and boundary accuracy ≥80% (±8 seconds).
- Q: How should YouTube upload quota reset timing be defined? → A: Use YouTube Data API semantics, with daily quota reset at Pacific Time 00:00 as the scheduling baseline.
- Q: How should detection quality metrics be defined in Success Criteria? → A: Split SC-002 into Recall and Boundary Accuracy for both modes, with explicit thresholds and tolerance windows.
- Q: How should audio content classification be implemented? → A: Use a lightweight pre-trained local audio classifier for music/speech/applause as a required detection signal.
- Q: How should SC-011 be aligned with daily upload quota limits? → A: Evaluate same-session completion for up to quota-sized uploads (6/day) and require automatic queued-resume behavior for excess items.
- Q: What local rule should match form responses to segments when cloud matching is unavailable? → A: Use deterministic weighted matching on normalized performer name and piece title, with program-order tie-break and manual review for unresolved cases.
- Q: How should post-quota-reset upload resumption be handled? → A: Keep automatic queued-upload resumption as a required behavior and add explicit scheduler requirements.
- Q: How should “single session” be defined for SC-011 timing validation? → A: Define it as one continuous app runtime interval; any app restart starts a new session.
- Q: How should SC-011 benchmark conditions be made reproducible? → A: Use a fixed benchmark profile (6 upload-ready 1080p segments) plus explicit minimum network conditions and retry assumptions.
- Q: How should SC-011 wording align with FR-055 auto-resume conditions? → A: Explicitly include both cases in SC-011: auto-resume at PT00:00 while running, and auto-resume on next launch if closed at reset time.

## Requirements *(mandatory)*

### Functional Requirements

#### Architecture & Separation of Concerns

- **FR-001**: The system MUST enforce strict separation between presentation (UI), application orchestration, domain logic, and infrastructure adapters. No domain logic may depend directly on a UI framework.
- **FR-002**: All external service integrations (YouTube, Google Forms, Gemini AI) MUST be accessed through defined interfaces that can be substituted, mocked, or disabled independently.
- **FR-003**: Every module MUST remain under 1,000 lines of code; modules approaching this limit MUST be decomposed into cohesive subpackages.
- **FR-004**: API credentials (YouTube OAuth tokens, Google API keys, Gemini API keys) MUST be stored as plain-text JSON files in the application's config directory for this refactor scope, consistent with the checkpoint/configuration storage approach; secure-store mode is out of scope.
- **FR-005**: Credential JSON files MUST be stored in per-user application directories with filesystem permissions restricted to the current user account.
- **FR-006**: Raw credentials MUST be redacted from logs, UI error output, exported diagnostics, and backup artifacts unless the user explicitly opts into secret export.

#### Video Processing Pipeline

- **FR-010**: The system MUST accept one or more video files as input and concatenate multi-file recordings into a logical continuous timeline before detection.
- **FR-011**: The system MUST detect individual performance segments within a concert video using local-only methods (no external API calls for detection).
- **FR-012**: Performance detection MUST use full visual-audio fusion combining YOLO-based visual scene analysis (person/instrument detection, stage activity) with audio energy analysis and lightweight pre-trained local audio content classification (music/speech/applause). The YOLO visual detection component MUST be user-configurable to disable via a settings toggle for low-spec PCs; when disabled, detection falls back to audio-only mode with stable operation and a user-visible notice of reduced expected boundary accuracy.
- **FR-013**: The system MUST allow the user to review detected segment boundaries and manually adjust start/end times before export.
- **FR-014**: The system MUST export each detected segment as a separate video file with configurable output format and quality settings.

#### Audio Synchronization

- **FR-020**: The system MUST synchronize external microphone audio with video audio by automatically determining the time offset between the two recordings and aligning them.
- **FR-021**: The system MUST allow the user to configure the audio mix balance between video audio and microphone audio.
- **FR-022**: The system MUST handle the case where no external audio is provided, using only the video's embedded audio track.

#### Performance-to-Metadata Mapping

- **FR-030**: The system MUST support speech transcription of MC announcements locally using the Whisper small model (~460 MB). The model MUST be bundled inside the single installer artifact, without requiring install-time or first-run network downloads. Transcription targets Japanese speech for extracting announced piece titles and performer names.
- **FR-031**: The system MUST parse concert program PDFs to extract structured performance metadata (piece title, composer, performer names, performance order).
- **FR-032**: The system MUST match detected video segments to program entries using a combination of: sequential order, transcribed speech content, and optionally music-information lookup.
- **FR-033**: The system MUST present mapping results to the user for review, clearly highlighting uncertain or unmatched entries, and allow manual correction.
- **FR-034**: The system MUST integrate Google Form responses (performer preferences for privacy, display name, description) into the final metadata using deterministic weighted matching on normalized performer name and piece title; ties MUST be resolved by program order and unresolved matches MUST be flagged for manual review.
- **FR-035**: PDF parsing and form-response matching MAY use cloud AI (Gemini) for enrichment but MUST provide a functional local-only fallback and MUST clearly indicate when cloud services are unavailable.
- **FR-036**: Music-information lookup, when enabled, MUST use a bundled local music-metadata dictionary (title/composer/performer) curated by the development side from internet sources before release; runtime network retrieval in user environments is not allowed, and lookup MUST degrade gracefully to sequential/transcription/manual mapping when lookup data is unavailable.

#### Resume & Checkpointing

- **FR-040**: The system MUST save processing state at meaningful checkpoints (after concatenation, after detection, after audio synchronization, after each segment export, after mapping, after each upload).
- **FR-041**: The system MUST detect whether source inputs, configuration, or model identifiers/versions have changed since the last checkpoint and invalidate affected checkpoints accordingly.
- **FR-042**: For processing checkpoints, the system MUST allow the user to explicitly choose between resuming from checkpoint or restarting from scratch.
- **FR-043**: Checkpoint data MUST be persisted as plain-text JSON files in the application's config directory. Each checkpoint file MUST include sufficient information to reproduce results: a means of verifying that source inputs have not changed, the configuration values used, model identifiers/versions/hashes, and references to intermediate outputs.
- **FR-044**: The system MUST persist structured pipeline logs for each stage transition, including timestamp, operation identifier, checkpoint identifier (if any), input/output references, and resume/invalidated decision reasons.
- **FR-045**: Configuration changes during an active processing job MUST apply from the next segment boundary (or next stage start), and affected future checkpoints MUST be invalidated deterministically.
- **FR-046**: Checkpoint and temporary artifacts MUST follow a lifecycle policy: retain while jobs are resumable, auto-clean temporary artifacts after successful completion, and provide user controls for retention or purge.
- **FR-047**: The system MUST enforce one active processing job at a time unless explicit multi-project support is later specified; checkpoints and logs MUST remain project-scoped and isolated.

#### YouTube Upload

- **FR-050**: The system MUST upload processed videos to YouTube with metadata (title, description, tags, privacy setting, category) derived from the mapping step.
- **FR-051**: The system MUST track daily API quota usage and prevent uploads that would exceed the daily limit, queuing excess uploads until the YouTube quota reset point (Pacific Time 00:00).
- **FR-052**: The system MUST use resumable uploads to handle network interruptions without re-uploading completed portions.
- **FR-053**: The system MUST support playlist creation and assignment for concert groupings.
- **FR-054**: The system MUST display upload status for each video (pending, queued, uploading, completed, failed) with YouTube URLs for completed uploads.
- **FR-055**: Queued uploads MUST resume automatically at the quota reset point (Pacific Time 00:00) while the application is running; if the application is not running at reset time, queued uploads MUST auto-resume on next launch without requiring remapping.

#### User Interface

- **FR-060**: The system MUST provide a guided workflow with clear steps: Load → Process → Preview/Map → Upload, plus a Settings area.
- **FR-061**: The UI MUST remain responsive (no frozen windows) during all long-running operations, showing real-time progress with percentage, current operation, and estimated time remaining.
- **FR-062**: The system MUST display user-friendly error messages with actionable guidance when operations fail.
- **FR-063**: The preview/mapping screen MUST show video thumbnails, segment timecodes, and associated metadata side-by-side for quick review.
- **FR-064**: The UI MUST be implemented using the Flet framework, replacing the current customtkinter implementation. The migration must prioritize responsiveness, maintainability, and packaging compatibility with the standalone Windows installer.

#### Installer & Distribution

- **FR-070**: The system MUST be packageable as a standalone Windows installer that includes all runtime dependencies (no separate Python installation required).
- **FR-071**: The installer MUST provide all required local models (detection, transcription) without requiring install-time or first-run network downloads.
- **FR-072**: The installer MUST support clean upgrades that preserve user settings and schema-compatible checkpoint data; schema-breaking upgrades (including this refactor) MAY invalidate legacy checkpoints if regeneration rules are explicit and user-visible.

#### Performance & Resource Efficiency

- **FR-080**: The system MUST process video in a streaming/chunked manner that bounds peak memory usage regardless of input file size.
- **FR-081**: The system MUST leverage GPU hardware acceleration (NVENC) when available, with automatic fallback to CPU-only processing.
- **FR-082**: The system MUST report estimated time remaining for all long-running operations based on throughput of completed work.
- **FR-083**: The system MUST verify available disk space before starting export operations and warn the user if space is insufficient.

### Key Entities

- **Concert Project**: Top-level container for a single concert event. Contains references to source video files, optional external audio, program PDF, form responses, and all derived outputs. Key attributes: project name, event date, venue, source file paths, output directory, processing state.
- **Source Video**: A raw video file input. Key attributes: file path, duration, resolution, codec, creation timestamp, file hash (for change detection).
- **External Audio**: An optional high-quality microphone recording to synchronize with the video. Key attributes: file path, duration, format, sample rate, file hash.
- **Performance Segment**: A detected time range within the concatenated video corresponding to a single musical performance. Key attributes: start time, end time, detection confidence, detection signals used, exported file path (after export).
- **Checkpoint**: A snapshot of processing state at a given pipeline stage, persisted as a plain-text JSON file in the app config directory. Key attributes: stage identifier, timestamp, input file hashes, configuration snapshot, output references, validity status.
- **Program Entry**: A single item from the concert program PDF. Key attributes: performance order number, piece title, composer, performer names, ensemble/instrument.
- **Music Metadata Dictionary**: Bundled offline reference dataset curated before release for lookup assistance. Key attributes: normalized piece title, composer aliases, performer/ensemble aliases, source revision identifier.
- **Form Response**: A performer's response from the Google Form. Key attributes: performer name, piece title, privacy preference, display name override, custom description.
- **Video-Metadata Mapping**: The association between a Performance Segment and a Program Entry (and optionally a Form Response). Key attributes: segment reference, program entry reference, form response reference, match confidence, match method (sequential/transcription/lookup/manual), user-verified flag.
- **Upload Record**: Tracks the YouTube upload state for a single video. Key attributes: segment reference, YouTube video ID, upload status (pending/queued/uploading/completed/failed), privacy setting, playlist assignment, quota cost, error details.

## Constitution Alignment *(mandatory)*

- **CA-001 Architecture Boundaries (NON-NEGOTIABLE)**: This refactor introduces a strict four-layer architecture: Presentation (UI views and view-models), Application (orchestration and workflow coordination), Domain (video processing, audio sync, detection, mapping business rules), and Infrastructure (file I/O, FFmpeg execution, YouTube API client, Google API clients, model inference runners). Domain logic must not import UI or infrastructure modules directly; all cross-layer communication goes through defined interfaces. This is the primary structural deliverable of the refactor.

- **CA-002 Test-First Delivery (NON-NEGOTIABLE)**: Each component must be developed test-first. Unit tests for domain logic (detection algorithms, audio sync, mapping heuristics) must achieve ≥90% line coverage. Integration tests must cover cross-module workflows: video-load-to-segment-export, segment-to-metadata-mapping, and upload-with-quota-management. Regression tests must be added for every bug discovered during development.

- **CA-003 Deterministic Processing, Observability & Resume**: Video segmentation must produce identical segment boundaries given the same input video, configuration, and model versions. All processing steps must emit structured log entries with timestamps, operation identifiers, and input/output references. The checkpoint system (FR-040–FR-043) directly implements the resume requirement. Checkpoints are invalidated when input file hashes, configuration values, or model versions change.

- **CA-004 Local-First Execution**: Performance detection, audio synchronization, speech transcription, and segment export must execute entirely locally. Gemini AI for PDF parsing and form matching is optional and failure-aware: if unavailable, the system falls back to local heuristics (sequential matching, keyword extraction). All external-service calls are behind interfaces that can be disabled or manually overridden. GPU acceleration is opportunistic with CPU fallback. Memory-efficient streaming is required for large files.

- **CA-005 Quality Gates**: All code must pass `uv run ruff check .`, `uv run pyright`, and `uv run pytest --cov` before merge. Minimum test coverage threshold: 80% overall, 90% for domain modules. These gates must run in CI (GitHub Actions) and be reproducible locally.

- **CA-006 Migration/Regeneration**: The refactor replaces the existing flat-file configuration, upload-state tracking, and processing state management. Old configuration files (JSON-based ConfigManager) MUST be migrated automatically on first launch of the new version, requiring no manual intervention. Legacy checkpoint files are invalidated and regenerated under the new format. Upload state (`upload_state.json`) MUST be migrated to the new upload persistence model (`uploads.json`, with upload checkpoints regenerated as needed) as part of the same auto-migration process.

- **CA-007 Module Size**: The current app.py (957 lines), google_form_connector.py (665 lines), and youtube_uploader.py (555 lines) should be decomposed for boundary clarity and maintainability, while the architecture enforces <1,000 lines per module as a hard limit. Automated checks in CI should flag modules exceeding the limit.

- **CA-008 Review Evidence**: Code review must include at least two independent review perspectives (e.g., architecture/boundaries review and correctness/domain-logic review). Reviews must confirm constitution compliance and attach quality-gate evidence (CI pass screenshot or log link) before merge.

- **CA-009 Design Discipline**: DRY is enforced by extracting shared infrastructure (authentication, configuration, file I/O) into reusable modules rather than duplicating across youtube_uploader, google_form_connector, and create_google_form. KISS is enforced by the decomposition strategy: each class has a single responsibility. OOP domain boundaries are maintained through explicit interface contracts between layers.

- **CA-010 Toolchain Discipline**: All dependency management uses `uv`. All program execution uses `uv run`. The build/packaging pipeline for the installer also uses `uv` for dependency resolution. No pip, conda, or manual dependency management is permitted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can process a 2-hour concert video (1080p) from raw input to exported segments in under 60 minutes on reference hardware (RTX 3060-class GPU), and under 150 minutes on CPU-only execution.
- **SC-002**: Performance segment detection achieves mode-specific metrics on a reference test set of at least 3 concert recordings with known ground-truth timestamps. Recall is defined as detected performances divided by ground-truth performances. Boundary accuracy is defined using one-to-one highest-overlap matching between detected and ground-truth segments, then computing the fraction of matched detected segments whose start/end are both within tolerance. Full visual-audio mode MUST reach recall ≥90% and boundary accuracy ≥90% within ±5 seconds. Audio-only fallback mode MUST reach recall ≥80% and boundary accuracy ≥80% within ±8 seconds.
- **SC-003**: Video-to-metadata mapping achieves ≥80% correct automatic matches (measured against manual ground truth) when MC announcements are present and a program PDF is provided.
- **SC-004**: Users can resume an interrupted processing job and reach completion without re-processing already-completed segments, verified by total processing time for resumed job being less than 50% of full re-processing time.
- **SC-005**: Peak memory usage during processing stays below 4 GB for 4K source video and below 2 GB for 1080p source video.
- **SC-006**: The UI remains responsive (responds to user interaction within 500 ms) during all background processing operations.
- **SC-007**: The application can be installed from a standalone installer on a clean Windows 10/11 machine (no preconfigured developer runtime/toolchain) and launch successfully within 5 seconds.
- **SC-008**: Automated test suite achieves ≥80% overall code coverage and ≥90% coverage of domain logic modules.
- **SC-009**: No module in the codebase exceeds 1,000 lines of code.
- **SC-010**: All mandated static analysis, type-checking, and automated test gates pass with zero errors in CI.
- **SC-011**: Under a daily quota of 6 uploads, the workflow can upload 6 upload-ready segment videos in a single session (one continuous app runtime interval, no restart) in under 2 hours using this fixed benchmark: six 1080p segments totaling 6-8 GB, minimum sustained uplink 50 Mbps, stable network (packet loss <1%), and no more than one transient retry per upload. Any excess prepared videos are queued with persisted state and resume automatically after Pacific Time quota reset while the app is running, or auto-resume on next launch if the app was closed at reset time, without remapping.
- **SC-012**: 100% of pipeline stage transitions produce structured log records containing operation identifiers, timestamps, and resume/invalidated decision reasons, verified on reference processing runs.
- **SC-013**: Credential files pass security checks for per-user file-permission restriction, and security tests confirm no raw secrets appear in logs or exported diagnostics.
- **SC-014**: After successful workflow completion, automatic cleanup reduces temporary artifact usage to less than 10% of source video size while preserving user-selected retention artifacts.
