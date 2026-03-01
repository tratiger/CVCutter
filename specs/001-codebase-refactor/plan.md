# Implementation Plan: CVCutter Full Architecture Refactor

**Branch**: `001-codebase-refactor` | **Date**: 2026-03-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-codebase-refactor/spec.md`

## Summary

Full architecture refactor of CVCutter — a concert video splitting, audio synchronization, metadata mapping, and YouTube upload orchestration desktop tool. The refactor introduces strict four-layer architecture with inward dependencies (Presentation/Application orchestrate Domain via Infrastructure adapters implementing domain ports), migrates the UI from customtkinter to Flet, adds multimodal performance-segment detection (YOLO visual + audio energy + audio content classification), integrates local Whisper speech transcription for metadata mapping, implements checkpoint/resume with structured logging, enforces test-first development with ≥80% overall / ≥90% domain coverage, and packages everything into a standalone Windows installer with bundled local models (<2 GB total).

## Technical Context

**Language/Version**: Python ≥3.11 (development on 3.13 per `.python-version`)
**Primary Dependencies**: Flet (UI, replacing customtkinter), FFmpeg/imageio-ffmpeg (video encoding), OpenCV (visual analysis), Ultralytics YOLOv8n (person/instrument detection), librosa + scipy (audio analysis), onnxruntime (audio classifier inference), openai-whisper + torch/torchaudio (speech transcription), google-api-python-client + google-auth-oauthlib (YouTube/Forms APIs), google-generativeai (optional Gemini enrichment), PyInstaller (installer packaging)
**Storage**: Plain-text JSON for mutable app state in per-user app config directory (checkpoints, configuration, upload state, credentials), plus bundled read-only SQLite reference dictionary for music lookup
**Testing**: pytest + pytest-cov (≥80% overall, ≥90% domain), pyright (static type checking), ruff (linting)
**Target Platform**: Windows 10/11 desktop (primary); architecture must not preclude future cross-platform
**Project Type**: Desktop application (standalone installer)
**Performance Goals**: 2h 1080p concert in <60 min (GPU) / <150 min (CPU); UI response <500 ms during processing; segment detection must satisfy both SC-002 metrics: visual-audio recall ≥90% and boundary accuracy ≥90% within ±5s, audio-only recall ≥80% and boundary accuracy ≥80% within ±8s
**Constraints**: Peak memory <4 GB (4K) / <2 GB (1080p); installer bundle <2 GB total model weight; daily YouTube quota ~6 uploads; SC-011 benchmark uses one continuous app runtime interval (no restart), six upload-ready 1080p segments totaling 6–8 GB, minimum sustained uplink 50 Mbps, packet loss <1%, and no more than one transient retry per upload (benchmark condition only; runtime retry policy follows spec edge-case behavior with resumable upload + exponential backoff); excess uploads must auto-resume at PT 00:00 while running or on next launch if closed at reset; all detection fully local (no external APIs); all user-facing UI strings remain Japanese by default
**Scale/Scope**: Single-user workstation; 1–20 video files per concert; ~5,200 LOC current → estimated 8,000–12,000 LOC refactored across layered packages; 5 primary UI screens (Load, Process, Preview/Map, Upload, Settings)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Boundary plan enforces separation of presentation, application orchestration,
      domain, and infrastructure adapters (NON-NEGOTIABLE).
      *Evidence: Four-layer package structure defined below — `src/cvcutter/presentation/`, `src/cvcutter/application/`, `src/cvcutter/domain/`, `src/cvcutter/infrastructure/`. Domain imports neither UI nor infrastructure directly; all cross-layer communication via protocol/ABC interfaces.*
- [x] Test strategy defines failing tests first and required regression coverage,
      including integration tests for cross-module workflows (NON-NEGOTIABLE).
      *Evidence: Test structure under `tests/unit/`, `tests/integration/`, `tests/contract/`. TDD workflow mandated (red → green → refactor). Integration tests cover video-to-export, segment-to-mapping, upload-with-quota pipelines. Regression tests required before any bug-fix merge.*
- [x] Design covers deterministic, reproducible processing from recorded inputs and
      persisted metadata, plus structured logs/checkpoints and resume invalidation
      when inputs or configuration change.
      *Evidence: Checkpoint service with JSON state per pipeline stage; input-hash + config-hash + model-version validation on resume; structured logging with operation ID, timestamps, and decision reasons at every stage transition.*
- [x] Core workflows remain local-first; external AI dependencies are optional,
      failure-aware, and manually overridable; design addresses memory-efficient
      processing and validated hardware acceleration use.
      *Evidence: Detection pipeline is fully local (YOLO + audio classifiers). Gemini is behind an optional enrichment interface with local fallback. Streaming/chunked video processing bounds memory. GPU via NVENC with CPU fallback.*
- [x] Quality gates are planned with `uv run ruff check .`, `uv run pyright`,
      and `uv run pytest --cov`.
      *Evidence: All three gates defined as mandatory pre-merge checks; CI workflow to be created in `.github/workflows/`.*
- [x] Dependency management and project command execution are defined through `uv`.
      *Evidence: All commands use `uv run`. No pip/conda. `pyproject.toml` is the single dependency specification.*
- [x] Plan defines migration or regeneration steps when storage or metadata formats change.
      *Evidence: Auto-migration service runs on first launch; converts legacy `app_config.json` and `upload_state.json` to the new schema/persistence model. Legacy checkpoints are invalidated and regenerated.*
- [x] Plan enforces module-size policy: files over 1000 lines are split or decomposed.
      *Evidence: Current `app.py` (957 lines) is decomposed into presentation layer subpackages. Hard limit enforced by `tools/check_module_size.py` in local/CI quality gates.*
- [x] Plan includes independent review perspectives and review-evidence collection before merge.
      *Evidence: Dual-perspective code review (architecture/boundaries + correctness/domain-logic) using multiple AI models, with CI pass evidence attached per CA-008.*
- [x] Plan documents DRY, KISS, and OOP adherence alongside domain boundaries.
      *Evidence: Shared infrastructure extracted to reusable modules (auth, config, file I/O). Single-responsibility classes throughout. Interface contracts between layers enforce OOP boundaries per CA-009.*

## Project Structure

### Documentation (this feature)

```text
specs/001-codebase-refactor/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── cli-contracts.md
│   └── service-interfaces.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/cvcutter/
├── __init__.py
├── main.py                          # Application entry point (replaces run_app.py)
│
├── domain/                          # Pure business logic — NO UI or I/O imports
│   ├── __init__.py
│   ├── models/                      # Domain entities and value objects
│   │   ├── __init__.py
│   │   ├── project.py               # ConcertProject, SourceVideo, ExternalAudio, ProjectConfig, ProcessingState
│   │   ├── segment.py               # PerformanceSegment, DetectionSignal, SignalType, ExportStatus
│   │   ├── metadata.py              # ProgramEntry, FormResponse, VideoMetadataMapping, MatchSignal, MatchMethod, MatchSignalType, PrivacySetting
│   │   ├── dictionary.py            # MusicMetadataDictionary
│   │   ├── checkpoint.py            # Checkpoint, PipelineStage, CheckpointStatus
│   │   └── upload.py                # UploadRecord, QuotaState, UploadStatus
│   ├── detection/                   # Performance-segment detection algorithms
│   │   ├── __init__.py
│   │   ├── detector.py              # Composite detector orchestrator
│   │   ├── audio_classifier.py      # Music/speech/applause classification
│   │   ├── audio_energy.py          # Energy-based onset/offset detection
│   │   └── visual_detector.py       # YOLO-based person/instrument detection
│   ├── audio/                       # Audio synchronization algorithms
│   │   ├── __init__.py
│   │   └── sync.py                  # Cross-correlation offset finder
│   ├── mapping/                     # Video-to-metadata matching
│   │   ├── __init__.py
│   │   ├── transcription.py         # Whisper transcript → match signals
│   │   ├── pdf_extraction.py        # Program PDF text blocks → ProgramEntry normalization logic
│   │   ├── form_matching.py         # FormResponse → segment weighted matching
│   │   ├── music_lookup.py          # Bundled dictionary scoring logic (service-backed)
│   │   └── composite_mapper.py      # Multi-signal fusion and confidence scoring
│   └── services/                    # Domain service interfaces (protocols/ABCs)
│       ├── __init__.py
│       ├── types.py                 # Service-boundary DTOs shared across ports
│       ├── video_io.py              # Protocol: video read/write/transcode
│       ├── model_runner.py          # Protocol: ML model inference
│       ├── checkpoint_store.py      # Protocol: checkpoint persistence
│       ├── project_store.py         # Protocol: project aggregate persistence
│       ├── quota_state_store.py     # Protocol: global quota-state persistence
│       ├── pdf_text_extractor.py    # Protocol: local PDF text extraction
│       ├── music_lookup.py          # Protocol: bundled music dictionary lookup
│       ├── form_data_service.py     # Protocol: form-response ingestion (CSV/API)
│       ├── upload_service.py        # Protocol: video upload
│       ├── credential_store.py      # Protocol: credential read/write
│       └── ai_enrichment.py         # Protocol: optional cloud AI enrichment
│
├── application/                     # Orchestration — coordinates domain + infra
│   ├── __init__.py
│   ├── pipeline.py                  # Main processing pipeline orchestrator
│   ├── upload_workflow.py           # Upload + quota management workflow
│   ├── mapping_workflow.py          # Detection → mapping → review workflow
│   ├── migration_service.py         # Legacy config/state auto-migration
│   └── checkpoint_manager.py        # Checkpoint validation, invalidation, resume logic
│
├── infrastructure/                  # Adapters for external systems
│   ├── __init__.py
│   ├── ffmpeg/                      # FFmpeg video I/O adapter
│   │   ├── __init__.py
│   │   ├── transcoder.py            # Implements video_io protocol
│   │   └── gpu_detect.py            # NVENC availability detection
│   ├── models/                      # ML model runners
│   │   ├── __init__.py
│   │   ├── yolo_runner.py           # YOLOv8n inference adapter
│   │   ├── whisper_runner.py        # Whisper speech-to-text adapter
│   │   └── audio_classifier_runner.py  # Audio content classifier adapter
│   ├── pdf/                         # Local PDF extraction adapters
│   │   ├── __init__.py
│   │   └── local_extractor.py       # Implements pdf_text_extractor protocol
│   ├── music/                       # Bundled dictionary lookup adapters
│   │   ├── __init__.py
│   │   └── sqlite_lookup.py         # Implements music_lookup protocol
│   ├── youtube/                     # YouTube Data API adapter
│   │   ├── __init__.py
│   │   ├── client.py                # Implements upload_service protocol
│   │   └── auth.py                  # OAuth2 flow
│   ├── forms/                       # Form-response composite adapter
│   │   ├── __init__.py
│   │   └── form_data_service.py     # Implements form_data_service protocol
│   ├── csv/                         # Local CSV ingestion adapters
│   │   ├── __init__.py
│   │   └── form_csv_loader.py       # Local CSV loader used by form_data_service
│   ├── google/                      # Google Forms/Sheets API adapter
│   │   ├── __init__.py
│   │   ├── forms_client.py          # Remote fetch component for form_data_service (Forms API)
│   │   └── sheets_client.py         # Remote fetch component for form_data_service (Sheets API)
│   ├── gemini/                      # Optional Gemini enrichment adapter
│   │   ├── __init__.py
│   │   └── client.py                # Implements ai_enrichment protocol
│   ├── persistence/                 # File-system persistence
│   │   ├── __init__.py
│   │   ├── json_checkpoint_store.py # Implements checkpoint_store protocol
│   │   ├── json_project_store.py    # Implements project_store protocol
│   │   ├── json_quota_state_store.py # Implements quota_state_store protocol
│   │   ├── json_config.py           # Configuration read/write
│   │   └── json_credential_store.py # Implements credential_store protocol
│   └── logging/                     # Structured logging infrastructure
│       ├── __init__.py
│       └── structured_logger.py     # JSON structured log emitter
│
├── presentation/                    # Flet-based UI layer
│   ├── __init__.py
│   ├── app.py                       # Flet application shell and navigation
│   ├── viewmodels/                  # View-models bridging UI ↔ application
│   │   ├── __init__.py
│   │   ├── load_vm.py               # Load/import screen state
│   │   ├── process_vm.py            # Processing screen state
│   │   ├── preview_vm.py            # Preview/mapping screen state
│   │   ├── upload_vm.py             # Upload screen state
│   │   └── settings_vm.py           # Settings screen state
│   └── views/                       # Flet UI views (pages)
│       ├── __init__.py
│       ├── load_view.py             # File selection and project setup
│       ├── process_view.py          # Processing progress and controls
│       ├── preview_view.py          # Segment preview and mapping review
│       ├── upload_view.py           # Upload status and queue management
│       └── settings_view.py         # Configuration editing
│
└── shared/                          # Cross-cutting utilities (no domain logic)
    ├── __init__.py
    ├── types.py                     # Shared type aliases and enums
    ├── hashing.py                   # File hash computation for change detection
    └── time_utils.py                # Timestamp and duration helpers

tests/
├── conftest.py                      # Shared fixtures (test video stubs, config factories)
├── unit/
│   ├── domain/
│   │   ├── test_detection.py
│   │   ├── test_audio_sync.py
│   │   ├── test_mapping.py
│   │   ├── test_checkpoint.py
│   │   └── test_models.py
│   ├── application/
│   │   ├── test_pipeline.py
│   │   ├── test_upload_workflow.py
│   │   ├── test_checkpoint_manager.py
│   │   ├── test_mapping_workflow.py
│   │   └── test_migration_service.py
│   └── infrastructure/
│       ├── test_json_checkpoint_store.py
│       ├── test_json_config.py
│       └── test_ffmpeg_transcoder.py
├── integration/
│   ├── test_video_to_export.py      # Load → detect → export pipeline
│   ├── test_segment_to_mapping.py   # Detect → transcribe → map pipeline
│   └── test_upload_with_quota.py    # Upload → quota → resume pipeline
└── contract/
    ├── test_youtube_contract.py     # YouTube API adapter contract tests
    ├── test_gemini_contract.py      # Gemini adapter contract tests
    ├── test_forms_contract.py       # Google Forms adapter contract tests
    └── test_sheets_contract.py      # Google Sheets adapter contract tests

tools/
└── check_module_size.py             # Fails if any module exceeds 1000 LOC
```

**Structure Decision**: Single-project four-layer architecture under `src/cvcutter/` with domain, application, infrastructure, and presentation packages. This enforces the constitution's separation requirements (CA-001) while keeping the project as a single installable Python package. The `domain/` package has zero imports from `infrastructure/` or `presentation/`; all cross-layer communication uses Protocol-based interfaces defined in `domain/services/`.

## Complexity Tracking

> No NON-NEGOTIABLE violations. No complexity justifications required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | — | — |
