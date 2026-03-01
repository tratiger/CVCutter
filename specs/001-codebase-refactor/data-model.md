# Data Model: CVCutter Full Architecture Refactor

**Feature Branch**: `001-codebase-refactor`
**Created**: 2026-03-01
**Source**: [spec.md](spec.md), [research.md](research.md)

## Entity Relationship Overview

```text
ConcertProject ─────┬──── 1:N ──── SourceVideo
                     ├──── 0:1 ──── ExternalAudio
                     ├──── 0:N ──── PerformanceSegment
                     ├──── 0:N ──── ProgramEntry
                     ├──── 0:N ──── FormResponse
                     ├──── 0:N ──── Checkpoint
                     └──── 0:N ──── UploadRecord

PerformanceSegment ──┬──── 0:1 ──── VideoMetadataMapping ──┬── 0:1 ── ProgramEntry
                     │                                      └── 0:1 ── FormResponse
                     └──── 0:1 ──── UploadRecord
UploadRecord ────────────── 1:1 ──── VideoMetadataMapping

MusicMetadataDictionary (read-only) ── assists ── VideoMetadataMapping
```

Pipeline logs are persisted infrastructure records (JSONL) and are not modeled as domain entities in this data model.

---

## Entities

### ConcertProject

Top-level aggregate root. Represents a single concert processing job.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str (UUID)` | PK, immutable | Unique project identifier |
| `name` | `str` | required, max 200 | Project display name |
| `event_date` | `date \| None` | optional | Concert event date |
| `venue` | `str \| None` | optional, max 200 | Concert venue name |
| `source_videos` | `list[SourceVideo]` | required, ≥1 | Ordered list of input video files |
| `external_audio` | `ExternalAudio \| None` | optional | External microphone recording |
| `program_pdf_path` | `Path \| None` | optional | Source concert program PDF path |
| `form_source_path` | `Path \| None` | optional | Source form-response input path (CSV/API export) |
| `form_remote_id` | `str \| None` | optional | Google Form identifier when using remote fetch |
| `form_remote_sheet_id` | `str \| None` | optional | Google Sheet identifier when using remote fetch |
| `output_directory` | `Path` | required | Export destination directory |
| `config_snapshot` | `ProjectConfig` | required | Processing configuration at creation |
| `processing_state` | `ProcessingState` | required | Current pipeline state enum |
| `created_at` | `datetime` | auto-set, UTC | Project creation timestamp |
| `updated_at` | `datetime` | auto-set, UTC | Last modification timestamp |

**Validation Rules**:
- `source_videos` must contain at least one entry
- `output_directory` must be a valid, writable filesystem path
- `name` must not be empty or whitespace-only
- `program_pdf_path`, when present, must point to a readable PDF file
- `form_source_path`, when present, must point to a readable source file
- `form_remote_id` and/or `form_remote_sheet_id`, when present, must be non-empty identifiers

**State Transitions**:
```text
CREATED → CONCATENATING → DETECTING → SYNCING_AUDIO → READY_FOR_EXPORT → EXPORTING
  → MAPPING → READY_FOR_UPLOAD → UPLOADING → COMPLETED
                                                 ↓
                                               PAUSED (at any stage)
                                                 ↓
                                              FAILED (at any stage, with error context)
```

**Execution Note**: `DETECTING` and `SYNCING_AUDIO` are independent stages in the checkpoint dependency graph; this transition order is a serialized UI/runtime display sequence, and invalidation/resume behavior follows the dependency graph defined below.
**Resume Regression Note**: When checkpoints are invalidated, `ProcessingState` regresses to the earliest invalidated execution stage required for deterministic replay (while keeping completed, unaffected stages intact).
**Pause/Failure Recovery Note**: `resume_processing()` transitions `PAUSED` (or recoverable `FAILED`) projects to the earliest resumable checkpoint stage; `start_processing()` transitions `PAUSED`/`FAILED` projects to `CREATED` for full restart.

---

### SourceVideo

A raw video file input to the project.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str (UUID)` | PK, immutable | Unique identifier |
| `file_path` | `Path` | required, must exist | Absolute path to video file |
| `order_index` | `int` | required, ≥0 | Position in concatenation order |
| `duration_seconds` | `float` | ≥0 | Video duration in seconds |
| `resolution` | `tuple[int, int]` | (width, height) | Video resolution |
| `codec` | `str` | informational | Video codec identifier |
| `creation_timestamp` | `datetime \| None` | optional | File creation/recording time |
| `file_hash` | `str` | SHA-256 | Hash for change detection |
| `file_size_bytes` | `int` | ≥0 | File size for disk space checks |

**Validation Rules**:
- `file_path` must point to an existing, readable file
- `file_hash` is computed lazily on first access and cached
- `order_index` values must be unique within a project

---

### ExternalAudio

Optional high-quality microphone recording.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str (UUID)` | PK, immutable | Unique identifier |
| `file_path` | `Path` | required, must exist | Absolute path to audio file |
| `duration_seconds` | `float` | ≥0 | Audio duration |
| `format` | `str` | informational | Audio format (WAV, FLAC, etc.) |
| `sample_rate` | `int` | ≥0 | Sample rate in Hz |
| `file_hash` | `str` | SHA-256 | Hash for change detection |
| `sync_offset_seconds` | `float \| None` | computed | Time offset from video audio |

**Validation Rules**:
- `file_path` must point to an existing, readable audio file
- `sync_offset_seconds` is computed by the audio sync domain service

---

### PerformanceSegment

A detected time range corresponding to a single musical performance.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str (UUID)` | PK, immutable | Unique identifier |
| `segment_index` | `int` | ≥0, unique per project | Sequential position |
| `start_time_seconds` | `float` | ≥0 | Start time in concatenated timeline |
| `end_time_seconds` | `float` | > start_time | End time in concatenated timeline |
| `detection_confidence` | `float` | 0.0–1.0 | Overall detection confidence |
| `detection_signals` | `list[DetectionSignal]` | ≥1 | Signals that contributed to detection |
| `exported_file_path` | `Path \| None` | optional | Path to exported video file |
| `export_status` | `ExportStatus` | enum | NOT_EXPORTED / EXPORTING / EXPORTED / FAILED |
| `user_adjusted` | `bool` | default False | Whether user manually adjusted boundaries |

**Validation Rules**:
- `end_time_seconds` must be strictly greater than `start_time_seconds`
- `end_time_seconds - start_time_seconds` ≥ `min_duration_seconds` config value (default 30s)
- `segment_index` values must be unique and sequential within a project

**Manual Split Rules**:
- `split_segment(segment_id, split_time)` creates two segments with new UUIDs and reassigns sequential `segment_index` values from the split point onward.
- Manual splits mark affected segments as `user_adjusted=True` and preserve upstream detection checkpoint provenance as user-overridden output.
- Per-segment checkpoints at/after the split point are re-addressed to the new indices and downstream export/mapping/upload checkpoints are invalidated for affected segments.
- `DetectionSignal` ranges are re-associated to child segments by time overlap; signals crossing the split point are partitioned to both children.

---

### DetectionSignal

Value object recording a single detection channel's contribution.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `signal_type` | `SignalType` | enum | VISUAL_YOLO / AUDIO_ENERGY / AUDIO_CLASSIFIER |
| `confidence` | `float` | 0.0–1.0 | Signal-specific confidence |
| `start_time_seconds` | `float` | ≥0 | Signal's detected start |
| `end_time_seconds` | `float` | > start_time | Signal's detected end |
| `metadata` | `dict[str, Any]` | optional | Signal-specific details (e.g., YOLO class counts) |

---

### ProgramEntry

A single item parsed from the concert program PDF.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str (UUID)` | PK, immutable | Unique identifier |
| `order_number` | `int` | ≥1 | Position in program order |
| `piece_title` | `str` | required | Musical work title |
| `composer` | `str \| None` | optional | Composer name |
| `performer_names` | `list[str]` | ≥0 | Performer/ensemble names |
| `ensemble` | `str \| None` | optional | Ensemble/group name |
| `instrument` | `str \| None` | optional | Primary instrument |
| `raw_text` | `str` | preserved | Original extracted text |

**Validation Rules**:
- `piece_title` must not be empty
- `order_number` values must be unique within a project

---

### FormResponse

A performer's response from the Google Form.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str (UUID)` | PK, immutable | Unique identifier |
| `performer_name` | `str` | required | Respondent performer name |
| `piece_title` | `str` | required | Associated piece title |
| `privacy_preference` | `PrivacySetting` | enum | PUBLIC / UNLISTED / PRIVATE |
| `display_name_override` | `str \| None` | optional | Preferred YouTube display name |
| `custom_description` | `str \| None` | optional | Performer-provided description text |
| `raw_data` | `dict[str, str]` | preserved | Original form fields |

**Validation Rules**:
- `performer_name` and `piece_title` must not be empty
- `privacy_preference` defaults to PUBLIC if not specified

---

### MusicMetadataDictionary

Read-only bundled reference dataset used by lookup-based mapping.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `revision_id` | `str` | required, immutable | Dictionary source revision identifier |
| `source_summary` | `str` | required | Curation/source description for auditability |
| `generated_at_utc` | `datetime` | required | Dictionary build timestamp |
| `entry_count` | `int` | ≥0 | Total indexed works/performers |

**Validation Rules**:
- `revision_id` must be persisted and exposed to mapping/checkpoint records for reproducibility
- Dictionary is read-only at runtime; no user-environment network refresh is allowed

---

### VideoMetadataMapping

Association between a PerformanceSegment and its metadata sources.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str (UUID)` | PK, immutable | Unique identifier |
| `segment_id` | `str` | FK → PerformanceSegment | Associated segment |
| `program_entry_id` | `str \| None` | FK → ProgramEntry | Matched program entry |
| `form_response_id` | `str \| None` | FK → FormResponse | Matched form response |
| `match_confidence` | `float` | 0.0–1.0 | Overall match confidence |
| `match_method` | `MatchMethod` | enum | SEQUENTIAL / TRANSCRIPTION / LOOKUP / MANUAL |
| `match_signals` | `list[MatchSignal]` | ≥0 | Individual signal contributions |
| `user_verified` | `bool` | default False | Whether user confirmed this mapping |
| `final_title` | `str` | required before upload | Resolved YouTube title |
| `final_description` | `str` | required before upload | Resolved YouTube description |
| `final_privacy` | `PrivacySetting` | computed | Resolved privacy setting |
| `final_category_id` | `str` | computed, default `"10"` | Resolved YouTube category |
| `final_tags` | `list[str]` | computed | Resolved YouTube tags |

**Validation Rules**:
- At least one of `program_entry_id` or manual user assignment must be present before upload
- `user_verified` must be True before upload when `match_confidence` is below `ProjectConfig.mapping_review_threshold` (default 0.8)
- `final_title` and `final_description` must be materialized before transition to `READY_FOR_UPLOAD`
- `final_category_id` must be materialized before transition to `READY_FOR_UPLOAD`
- `final_privacy` is derived from the selected `form_response_id` when present; otherwise defaults to PUBLIC
- If multiple form responses are candidates for one segment, deterministic weighted matching selects one authoritative `form_response_id`; unresolved conflicts require manual assignment before `READY_FOR_UPLOAD`

---

### MatchSignal

Value object recording a single matching signal's contribution.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `signal_type` | `MatchSignalType` | enum | SEQUENTIAL_ORDER / TRANSCRIPTION / MUSIC_LOOKUP / FORM_MATCH |
| `confidence` | `float` | 0.0–1.0 | Signal confidence |
| `evidence` | `str` | informational | What was matched (e.g., transcribed text) |

---

### Checkpoint

Processing state snapshot at a pipeline stage.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str (UUID)` | PK, immutable | Unique checkpoint identifier |
| `project_id` | `str` | FK → ConcertProject | Associated project |
| `stage` | `PipelineStage` | enum | Pipeline stage this checkpoint covers |
| `status` | `CheckpointStatus` | enum | VALID / INVALIDATED / IN_PROGRESS |
| `created_at` | `datetime` | auto-set, UTC | Checkpoint creation time |
| `input_hashes` | `dict[str, str]` | required | Map of input file paths → SHA-256 hashes |
| `config_snapshot` | `dict[str, Any]` | required | Relevant configuration values at checkpoint time |
| `model_versions` | `dict[str, str]` | required | Model name → version/hash |
| `output_references` | `list[str]` | ≥0 | Paths to intermediate output files |
| `segment_index` | `int \| None` | optional | For per-segment stages (EXPORT, UPLOAD) |
| `error_detail` | `str \| None` | optional | Error message if stage failed |

**Validation Rules**:
- `input_hashes` must not be empty
- `config_snapshot` must include all configuration values relevant to the stage
- `model_versions` must include entries for all models used in the stage

**State Transitions**:
```text
IN_PROGRESS → VALID (stage completed successfully)
IN_PROGRESS → INVALIDATED (stage failed or inputs changed)
VALID → INVALIDATED (downstream change or user request)
```

---

### UploadRecord

YouTube upload state for a single video segment.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str (UUID)` | PK, immutable | Unique identifier |
| `segment_id` | `str` | FK → PerformanceSegment | Associated segment |
| `mapping_id` | `str` | FK → VideoMetadataMapping | Associated mapping |
| `youtube_video_id` | `str \| None` | optional | YouTube video ID after upload |
| `upload_status` | `UploadStatus` | enum | PENDING / UPLOADING / COMPLETED / FAILED / QUEUED |
| `privacy_setting` | `PrivacySetting` | enum | PUBLIC / UNLISTED / PRIVATE |
| `playlist_id` | `str \| None` | optional | Target YouTube playlist ID |
| `quota_cost` | `int` | default 1600 | Estimated quota units for this upload |
| `retry_count` | `int` | default 0, max 5 | Number of retry attempts |
| `error_detail` | `str \| None` | optional | Last error message |
| `resumable_upload_uri` | `str \| None` | optional | YouTube resumable upload URI |
| `bytes_uploaded` | `int` | default 0 | Bytes uploaded so far (for resume) |
| `youtube_url` | `str \| None` | computed | Full YouTube watch URL |
| `uploaded_at` | `datetime \| None` | optional | Upload completion timestamp |

**State Transitions**:
```text
PENDING → UPLOADING → COMPLETED
PENDING → QUEUED (quota exhausted)
UPLOADING → FAILED (network error after max retries)
UPLOADING → QUEUED (quota exhausted mid-upload)
QUEUED → PENDING (quota reset)
FAILED → PENDING (manual retry)
```

---

### QuotaState

Value object tracking YouTube API daily quota.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `daily_limit` | `int` | default 10000 | Daily quota unit limit |
| `daily_used` | `int` | ≥0 | Units consumed today |
| `reset_timestamp_utc` | `datetime` | required | Next PT 00:00 in UTC |
| `last_updated` | `datetime` | auto-set | Last quota state update |

---

### ProjectConfig

Value object holding project-level processing configuration.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `video_audio_volume` | `float` | 0.0–2.0, default 0.6 | Video audio mix level |
| `mic_audio_volume` | `float` | 0.0–2.0, default 1.5 | Mic audio mix level |
| `audio_sync_sample_rate` | `int` | default 22050 | Sample rate for sync analysis |
| `enable_yolo_detection` | `bool` | default True | Enable YOLO visual detection |
| `min_segment_duration_seconds` | `float` | ≥10, default 30 | Minimum performance duration |
| `output_format` | `str` | default "mp4" | Export file format |
| `output_quality` | `str` | default "high" | Export quality preset |
| `enable_gpu` | `bool` | default True | Enable GPU acceleration |
| `enable_gemini` | `bool` | default True | Enable optional Gemini enrichment |
| `gemini_model` | `str` | default "gemini-2.5-flash" | Gemini model identifier |
| `youtube_chunk_size` | `int` | default 5242880 | Upload chunk size in bytes |
| `mapping_review_threshold` | `float` | 0.0–1.0, default 0.8 | Confidence threshold requiring user verification |

---

## Enumerations

| Enum | Values |
|------|--------|
| `ProcessingState` | CREATED, CONCATENATING, DETECTING, SYNCING_AUDIO, READY_FOR_EXPORT, EXPORTING, MAPPING, READY_FOR_UPLOAD, UPLOADING, COMPLETED, PAUSED, FAILED |
| `PipelineStage` | CONCATENATION, DETECTION, AUDIO_SYNC, EXPORT, MAPPING, UPLOAD |
| `CheckpointStatus` | IN_PROGRESS, VALID, INVALIDATED |
| `ExportStatus` | NOT_EXPORTED, EXPORTING, EXPORTED, FAILED |
| `UploadStatus` | PENDING, UPLOADING, COMPLETED, FAILED, QUEUED |
| `PrivacySetting` | PUBLIC, UNLISTED, PRIVATE |
| `SignalType` | VISUAL_YOLO, AUDIO_ENERGY, AUDIO_CLASSIFIER |
| `MatchMethod` | SEQUENTIAL, TRANSCRIPTION, LOOKUP, MANUAL |
| `MatchSignalType` | SEQUENTIAL_ORDER, TRANSCRIPTION, MUSIC_LOOKUP, FORM_MATCH |

**Checkpoint Cascade Note**: "Downstream" checkpoint invalidation follows the stage dependency graph (research R-005), not raw enum order. Dependencies are: `CONCATENATION -> {DETECTION, AUDIO_SYNC}`, `DETECTION -> EXPORT`, `AUDIO_SYNC -> EXPORT`, `EXPORT -> MAPPING`, `MAPPING -> UPLOAD`. Invalidating `DETECTION` invalidates `EXPORT`, `MAPPING`, and `UPLOAD`, but does not invalidate `AUDIO_SYNC` unless sync-relevant inputs/configuration changed. Invalidating `AUDIO_SYNC` invalidates dependent `EXPORT`, `MAPPING`, and `UPLOAD` checkpoints. For per-segment invalidation, cascades apply only to checkpoints covering the same segment; global checkpoints are invalidated if any required segment contribution becomes invalid.

## JSON Persistence Format

Application state (checkpoints, config, upload state) is persisted as plain-text JSON in the per-user application config directory; reference assets are read-only and revision-validated:

```text
{LOCALAPPDATA}/cvcutter/
├── config.json                    # Global application configuration
├── projects/
│   └── {project_id}/
│       ├── project.json           # ConcertProject state
│       ├── segments.json          # PerformanceSegment list
│       ├── mappings.json          # VideoMetadataMapping list
│       ├── uploads.json           # UploadRecord list
│       ├── program_entries.json   # ProgramEntry list (parsed PDF)
│       ├── form_responses.json    # FormResponse list
│       └── checkpoints/
│           ├── concatenation.json
│           ├── detection.json
│           ├── audio_sync.json
│           ├── export_{index}.json
│           ├── mapping.json
│           └── upload_{index}.json
├── quota_state.json               # YouTube QuotaState (global)
├── reference/
│   └── music_dictionary.sqlite    # Bundled read-only dictionary index
├── credentials/                   # Per-user restricted directory
│   ├── youtube_oauth.json
│   ├── google_api_key.json
│   └── gemini_api_key.json
└── logs/
    └── pipeline_{project_id}.jsonl # Structured pipeline logs
```
