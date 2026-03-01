# UI & Entry Point Contracts: CVCutter Full Architecture Refactor

**Feature Branch**: `001-codebase-refactor`
**Created**: 2026-03-01
**Layer**: Presentation boundary (User-facing interfaces)

CVCutter is a desktop GUI application. It does not expose a functional public CLI API beyond command-based app launch entrypoints. This document defines the user-facing interface contracts: application entry points, Flet UI screen contracts, and the view-model contracts that bridge UI to application logic.

---

## Application Entry Points

### Desktop Launch

```text
Entry: src/cvcutter/main.py → main()
Method: uv run cvcutter  (via pyproject.toml [project.scripts])
         OR double-click CVCutter.exe (PyInstaller packaged)

Behavior:
  1. Initialize logging (structured JSON to {LOCALAPPDATA}/cvcutter/logs/)
  2. Run MigrationService.migrate_if_needed() for legacy config/state
  3. Launch Flet application with main window (1100×800, dark theme)
  4. Display Load screen as default view
```

### Development Commands

```text
# Run application
uv run cvcutter

# Run tests with coverage
uv run pytest --cov=src/cvcutter --cov-report=term-missing

# Static type checking
uv run pyright

# Lint checking
uv run ruff check .

# Build installer
uv run python build_exe.py
```

---

## UI Screen Contracts

Each screen corresponds to a Flet view + view-model pair. The view-model exposes observable state and command methods; the view binds to these.

### Screen 1: Load (ファイル読み込み)

**Purpose**: Select source video files, optional external audio, program PDF, and form responses.

| View-Model Property | Type | Description |
|---------------------|------|-------------|
| `video_files` | `list[Path]` | Selected video file paths (ordered) |
| `external_audio_file` | `Path \| None` | Optional mic audio path |
| `program_pdf_file` | `Path \| None` | Optional concert program PDF |
| `form_csv_file` | `Path \| None` | Optional Google Form CSV |
| `form_remote_id` | `str \| None` | Optional Google Form ID for remote fetch |
| `form_remote_sheet_id` | `str \| None` | Optional Google Sheet ID for remote fetch |
| `output_directory` | `Path` | Export destination |
| `project_name` | `str` | Project display name |
| `validation_errors` | `list[str]` | Current validation issues |
| `can_proceed` | `bool` | True when minimum inputs are valid |

| Command | Parameters | Effect |
|---------|-----------|--------|
| `add_videos()` | file dialog | Append to `video_files`, probe metadata |
| `remove_video(index)` | int | Remove from list |
| `reorder_videos(from, to)` | int, int | Change concatenation order |
| `set_external_audio()` | file dialog | Set mic audio file |
| `set_program_pdf()` | file dialog | Set PDF file |
| `set_form_csv()` | file dialog | Set form CSV file |
| `set_form_remote_source(form_id, sheet_id)` | str \| None, str \| None | Set optional remote Google Forms/Sheets source IDs |
| `create_project()` | — | Validate and create ConcertProject |

---

### Screen 2: Process (動画処理)

**Purpose**: Run the processing pipeline with progress feedback.

| View-Model Property | Type | Description |
|---------------------|------|-------------|
| `current_stage` | `PipelineStage` | Active processing stage |
| `stage_progress` | `float` | 0.0–1.0 within current stage |
| `overall_progress` | `float` | 0.0–1.0 across all stages |
| `estimated_time_remaining` | `str` | Human-readable ETA |
| `current_operation` | `str` | Description of current action |
| `detected_segments` | `list[SegmentSummary]` | Segments detected so far |
| `is_processing` | `bool` | True while pipeline is running |
| `is_resumable` | `bool` | True if valid checkpoints exist |
| `resume_info` | `ResumeInfo \| None` | Checkpoint state for resume prompt |
| `errors` | `list[str]` | Processing errors |
| `gpu_enabled` | `bool` | Whether GPU is active |

| Command | Parameters | Effect |
|---------|-----------|--------|
| `start_processing()` | — | Begin from scratch |
| `resume_processing()` | — | Resume from last checkpoint |
| `pause_processing()` | — | Pause at next stage boundary |
| `cancel_processing()` | — | Cancel current run, retain checkpoints, and transition to `PAUSED` with cancel reason |

---

### Screen 3: Preview & Map (プレビュー & 紐付け)

**Purpose**: Review detected segments, adjust boundaries, and manage metadata mapping.

| View-Model Property | Type | Description |
|---------------------|------|-------------|
| `segments` | `list[SegmentPreview]` | Segments with thumbnails |
| `mappings` | `list[MappingPreview]` | Current segment-metadata mappings |
| `program_entries` | `list[ProgramEntry]` | Available program entries |
| `form_responses` | `list[FormResponse]` | Available form responses |
| `unmatched_segments` | `list[str]` | Segment IDs without confident match |
| `uncertain_mappings` | `list[str]` | Mapping IDs below confidence threshold |
| `selected_segment_id` | `str \| None` | Currently selected segment |
| `cloud_enrichment_available` | `bool` | Whether optional cloud enrichment is currently reachable |
| `mapping_fallback_mode` | `bool` | True when local-only fallback mapping is active |
| `processing_state` | `ProcessingState` | Current workflow state for command gating |

| Command | Parameters | Effect |
|---------|-----------|--------|
| `select_segment(segment_id)` | str | Load preview for segment |
| `adjust_boundary(segment_id, start, end)` | str, float, float | Update segment boundaries (enabled in `READY_FOR_EXPORT` state) |
| `split_segment(segment_id, split_time)` | str, float | Split a long segment into two segments (enabled in `READY_FOR_EXPORT` state) |
| `assign_mapping(segment_id, program_entry_id)` | str, str | Manual program-entry assignment (enabled in `MAPPING` state) |
| `assign_form_response(segment_id, form_response_id)` | str, str | Manual form-response assignment (enabled in `MAPPING` state) |
| `clear_mapping(segment_id)` | str | Remove mapping from segment |
| `verify_mapping(segment_id)` | str | Mark mapping as user-verified |
| `auto_map()` | — | Run automatic mapping pipeline (enabled in `MAPPING` state) |
| `finalize_mappings()` | — | Validate mapping preconditions and transition to `READY_FOR_UPLOAD` |
| `export_segments()` | — | Export all segments to output directory (enabled in `READY_FOR_EXPORT` state) |

---

### Screen 4: Upload (アップロード)

**Purpose**: Upload exported segments to YouTube with quota management.

| View-Model Property | Type | Description |
|---------------------|------|-------------|
| `upload_records` | `list[UploadRecordView]` | Status for each segment upload |
| `quota_state` | `QuotaStateView` | Current quota usage and limits |
| `is_uploading` | `bool` | True during active uploads |
| `queued_count` | `int` | Number of uploads waiting for quota reset |
| `playlist_id` | `str \| None` | Target playlist |
| `processing_state` | `ProcessingState` | Current workflow state for command gating |
| `estimated_time_remaining` | `str` | Estimated time to complete current upload batch |
| `current_operation` | `str` | Description of current upload operation |

| Command | Parameters | Effect |
|---------|-----------|--------|
| `start_upload()` | — | Begin batch upload (enabled only in `READY_FOR_UPLOAD` with mappings below review-threshold explicitly verified and finalized metadata) |
| `pause_upload()` | — | Pause after current upload |
| `retry_failed(upload_record_id)` | str | Retry a specific failed upload |
| `create_playlist(title)` | str | Create YouTube playlist |
| `open_youtube(upload_record_id)` | str | Open uploaded video URL in browser |

---

### Screen 5: Settings (設定)

**Purpose**: Configure processing, detection, and API settings.

| View-Model Property | Type | Description |
|---------------------|------|-------------|
| `config` | `ProjectConfig` | Current configuration values |
| `youtube_authenticated` | `bool` | YouTube OAuth status |
| `gemini_configured` | `bool` | Gemini API key presence |
| `gpu_available` | `bool` | Whether GPU is detected |

| Command | Parameters | Effect |
|---------|-----------|--------|
| `update_config(key, value)` | str, Any | Update a config setting |
| `authenticate_youtube()` | — | Run OAuth2 flow |
| `test_gemini_connection()` | — | Verify Gemini API key |
| `set_artifact_retention(policy)` | str | Set checkpoint/temp artifact retention policy |
| `purge_artifacts(project_id)` | str | Purge checkpoints/temp artifacts for a project |
| `reset_to_defaults()` | — | Reset all settings to defaults |

---

## View-Model ↔ Application Layer Contract

View-models do NOT call infrastructure directly. They invoke application-layer services:

```text
ViewModel → ApplicationService → DomainService (via Protocol) → InfrastructureAdapter

Example flow:
  ProcessViewModel.start_processing()
    → PipelineOrchestrator.run(project, progress_callback)
      → CheckpointManager.validate_resume(project)
      → VideoIOService.concatenate(videos)  [Protocol → FFmpegTranscoder]
      → DetectionService.detect(audio, video_frames)  [Domain logic]
      → CheckpointStore.save(checkpoint)  [Protocol → JsonCheckpointStore]
```

**Progress Reporting**: Application services accept `Callable[[ProgressEvent], None]` callbacks. View-models translate these to Flet UI updates via `page.run_task()`.

**Error Handling**: Application services raise typed domain exceptions (`ProcessingError`, `UploadError`, `ConfigurationError`). View-models catch these and translate to user-friendly messages.
