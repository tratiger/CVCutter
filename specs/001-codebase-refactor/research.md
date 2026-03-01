# Research: CVCutter Full Architecture Refactor

**Feature Branch**: `001-codebase-refactor`
**Created**: 2026-03-01
**Status**: Complete

## R-001: Four-Layer Architecture Pattern for Python Desktop Applications

**Decision**: Adopt Ports-and-Adapters (Hexagonal) architecture expressed as four Python packages: `domain/`, `application/`, `infrastructure/`, `presentation/`. Domain defines Protocol-based interfaces (PEP 544 structural subtyping) in `domain/services/`; infrastructure and presentation implement those protocols.

**Rationale**: The constitution mandates strict separation (CA-001). Hexagonal architecture naturally prevents domain→infrastructure/UI coupling because the domain defines the interfaces and adapters depend inward. Python's `Protocol` class provides structural typing without requiring inheritance, keeping the domain package completely independent.

**Alternatives Considered**:
- **Django-style layered**: Not applicable — no web framework, and Django couples ORM to models.
- **Clean Architecture (Uncle Bob full form)**: Adds use-case interactors as a separate layer. Considered too heavy for a single-user desktop tool with ~10k LOC. The four-package structure achieves the same isolation without extra indirection.
- **Simple MVC**: Insufficient separation — MVC doesn't formalize the infrastructure adapter boundary, which is critical for testability of YouTube/FFmpeg/model integrations.

---

## R-002: UI Framework Migration — Flet vs. Alternatives

**Decision**: Migrate to Flet (Flutter-based Python UI framework) as specified in the clarifications (Q: UI framework → A: Flet).

**Rationale**: Flet provides responsive, modern UI via Flutter rendering while keeping the codebase pure Python. It supports desktop packaging (standalone executables), async/event-driven architecture, and built-in responsive layout — addressing all pain points with the current customtkinter approach (frozen windows during processing, dated appearance, limited layout capabilities).

**Alternatives Considered**:
- **customtkinter (current)**: Mature but produces dated-looking UIs; lacks native async support, causing UI freezes during long operations. Constitution requires responsive UI (FR-061).
- **PyQt6 / PySide6**: Powerful and mature, but GPL/LGPL licensing complexity; heavier dependency footprint; steeper learning curve for the maintenance team.
- **Dear PyGui**: High-performance immediate-mode rendering, but less suitable for form-heavy workflow UIs; smaller ecosystem.
- **Textual/Rich**: Terminal-based — doesn't meet the desktop GUI requirement.

**Integration Notes**:
- Flet's `page.run_task()` enables non-blocking background operations natively.
- View-model pattern maps cleanly to Flet's stateful control model.
- Flet packages via `flet pack` or PyInstaller (tested compatibility).

---

## R-003: Multimodal Performance-Segment Detection Strategy

**Decision**: Composite detector with three signal channels: (1) YOLO visual (person/instrument detection via YOLOv8n), (2) audio energy analysis (onset/offset envelope tracking), (3) lightweight audio content classifier (music/speech/applause discrimination). YOLO is user-toggleable; audio channels are always active.

**Rationale**: The spec mandates full visual-audio fusion (FR-012) with configurable YOLO disable and dual SC-002 metrics per mode: visual-audio recall ≥90% and boundary accuracy ≥90% within ±5s, and audio-only recall ≥80% and boundary accuracy ≥80% within ±8s. A composite pattern allows independent signal development, testing, and weight tuning.

**Alternatives Considered**:
- **Audio-only (energy thresholds)**: Simpler but insufficient for ≥90% boundary accuracy — audio energy alone can't reliably distinguish applause transitions from quiet performance sections.
- **Full video-frame CNN**: Computationally expensive; would require large model (>500 MB); not practical for low-spec PC toggle requirement.
- **External API (Gemini vision)**: Prohibited for detection by constitution (CA-004, FR-011).

**Implementation Approach**:
- **YOLO visual signal**: Run YOLOv8n at 1 FPS sampling rate on keyframes. Detect person count changes, instrument presence/absence. Output: confidence time-series of "stage activity level".
- **Audio energy signal**: Compute RMS energy + spectral centroid in sliding windows. Detect silence gaps (>3s below threshold) as potential boundaries.
- **Audio content classifier**: Lightweight pre-trained model (target ≤50 MB) classifying 1-second audio frames as music/speech/applause/silence. Provides semantic labeling for boundary decisions.
- **Fusion**: Weighted voting with configurable thresholds. State machine tracks segment boundaries: IDLE → PERFORMING → TRANSITION → IDLE. Boundary refinement applies hysteresis to prevent over-segmentation.

**Audio Content Classifier Selection**:
- **Primary candidate**: PANNs (Pretrained Audio Neural Networks) — CNN14 variant, ~80 MB but can be pruned/quantized to ≤50 MB. Pre-trained on AudioSet with strong music/speech/environmental sound classification. Operates on mel-spectrograms.
- **Alternative**: YAMNet (TensorFlow Lite, ~4 MB) — lighter but less accurate for music sub-classification. Would need TFLite runtime which adds packaging complexity.
- **Decision**: Use PANNs CNN14 (quantized to ≤50 MB) for superior classification accuracy. Bundle as ONNX for runtime portability and inference-only dependency.

---

## R-004: Whisper Integration for MC Speech Transcription

**Decision**: Use OpenAI Whisper "small" model (~461 MB) via the `openai-whisper` Python package for local Japanese speech transcription of MC announcements.

**Rationale**: Specified in clarifications. Whisper small offers strong Japanese accuracy while fitting the <2 GB total model budget. The model is bundled in the installer — no network fetch at runtime.

**Alternatives Considered**:
- **Whisper tiny** (~39 MB): Too low accuracy for Japanese speech, especially in noisy concert environments.
- **Whisper medium** (~1.5 GB): Better accuracy but exceeds model budget when combined with YOLO + audio classifier.
- **faster-whisper (CTranslate2)**: Faster inference and lower memory. Strong alternative worth evaluating during implementation — same model weights, just optimized runtime. May substitute if performance testing shows Whisper's default PyTorch inference is too slow.
- **Cloud STT (Google/Azure)**: Prohibited for core functionality by constitution (CA-004).

**Integration Pattern**: Whisper runs on detected MC/speech segments (identified by the audio content classifier) rather than the full audio stream. This dramatically reduces inference time — only process segments classified as "speech" between performances.

---

## R-005: Checkpoint/Resume Architecture

**Decision**: Pipeline-stage checkpoint system with JSON persistence, input-hash validation, and selective invalidation.

**Rationale**: Required by FR-040–FR-047 and CA-003. JSON persistence aligns with constitution's plain-text requirement. Stage-level granularity supports partial resume without full pipeline restart.

**Design**:
- **Pipeline stages (dependency graph)**: CONCATENATION → {DETECTION, AUDIO_SYNC} → EXPORT(per-segment) → MAPPING → UPLOAD(per-segment)
- **Checkpoint record**: `{ stage, timestamp, input_hashes: {file: sha256}, config_snapshot, model_versions, output_refs, status }`
- **Validation on resume**: Compare current input hashes + config + model versions against checkpoint record. If any mismatch, invalidate this checkpoint and all downstream.
- **Invalidation cascade**: Stage dependency graph ensures that invalidating DETECTION also invalidates EXPORT, MAPPING, and UPLOAD checkpoints.
- **One active job**: Enforced at application layer; checkpoints are project-scoped.
- **Lifecycle**: Retain while job is resumable; auto-clean temp artifacts after successful completion; user controls for manual purge.

**Alternatives Considered**:
- **SQLite persistence**: More structured but adds a dependency and violates the plain-text JSON requirement (FR-043).
- **Full event-sourcing**: Overkill for single-user desktop tool with ~10 pipeline stages.
- **Pickle-based**: Not human-readable; security concerns with arbitrary deserialization.

---

## R-006: Legacy Configuration Migration Strategy

**Decision**: Automatic one-time migration on first launch. A `MigrationService` in the application layer detects legacy files, transforms them to the new schema, and writes new-format files. Legacy files are renamed with `.legacy` suffix (not deleted) for safety.

**Rationale**: Required by CA-006 and the clarification that auto-migration must require no manual intervention. Preserving legacy files as `.legacy` provides a safety net without polluting the active config directory.

**Migration Targets**:
- `app_config.json` → root `{LOCALAPPDATA}/cvcutter/config.json`
- `upload_state.json` → per-project `uploads.json` (with upload checkpoints regenerated as needed)
- Legacy processing state → invalidated; users must reprocess (per CA-006)
- Google Forms pickle files → converted to JSON credential store format
- Form history JSON → preserved and linked into new project structure

---

## R-007: Installer Packaging with Bundled Models

**Decision**: PyInstaller-based standalone Windows installer (`.exe` or directory bundle). All local models (YOLOv8n ~6 MB, Whisper small ~461 MB, audio classifier ~50 MB) bundled as data files within the installer artifact.

**Rationale**: Current approach already uses PyInstaller (`build_exe.py`). Expanding it to include model files is straightforward. NSIS wrapper can create a proper Windows installer (Start Menu shortcut, uninstaller) around the PyInstaller output.

**Alternatives Considered**:
- **cx_Freeze**: Less ecosystem support for bundling ML model files.
- **Briefcase (BeeWare)**: Doesn't support bundling arbitrary binary data files as easily.
- **MSI via WiX**: More complex setup; PyInstaller + NSIS is simpler and meets requirements.

**Bundle Size Estimate**: Python runtime ~30 MB + dependencies ~200 MB + YOLOv8n 6 MB + Whisper small 461 MB + audio classifier 50 MB + Flet runtime ~50 MB ≈ **~800 MB** total (well under 2 GB).

---

## R-008: Structured Logging and Observability

**Decision**: Python `logging` module with JSON formatter emitting structured log records. Each pipeline stage transition emits a mandatory structured log entry containing: timestamp, operation ID, checkpoint ID, input/output references, and resume/invalidation decision reasons.

**Rationale**: Required by FR-044 and CA-003. JSON-structured logs enable machine parsing for audit and debugging. Python's built-in logging is sufficient — no need for external logging frameworks.

**Format**:
```json
{
  "timestamp": "ISO-8601",
  "level": "INFO",
  "operation_id": "uuid",
  "pipeline_stage": "DETECTION",
  "checkpoint_id": "chk_xxx",
  "event": "stage_complete",
  "input_refs": ["video_concat_001.mp4"],
  "output_refs": ["segments.json"],
  "decision": "resume_valid",
  "decision_reason": "input_hash_match + config_match",
  "duration_ms": 45230
}
```

---

## R-009: YouTube Quota Management and Auto-Resume

**Decision**: `QuotaManager` tracks daily usage against the 10,000-unit daily limit (each video upload costs ~1,600 units ≈ 6 uploads/day). Quota resets at Pacific Time 00:00. The upload workflow queues excess uploads with persisted state and schedules auto-resume via a background timer when the app is running, or automatically resumes queued uploads on next launch if the app was closed at reset time.

**Rationale**: Required by FR-051, FR-055, and SC-011. The existing `QuotaManager` in `youtube_uploader.py` already tracks quota — the refactored version persists global quota state and per-project upload queue state, then adds the auto-resume scheduler.

**Implementation**:
- Quota state persisted globally in `quota_state.json`: `{ daily_limit, daily_used, reset_timestamp_utc, last_updated }`
- Background scheduler checks system time against PT 00:00 and triggers resume
- Queued uploads are persisted in per-project `uploads.json` (`UploadStatus=QUEUED`) and auto-resume on next launch without remapping
- Resumable uploads via YouTube API's `resumable=True` parameter (already partially implemented)

---

## R-010: Memory-Efficient Video Processing

**Decision**: Streaming/chunked processing throughout the pipeline. Video frames read one-at-a-time (or in small batches) via FFmpeg pipe. Audio processed in windowed chunks. No full-video-in-memory loading.

**Rationale**: Required by FR-080 and SC-005 (peak <4 GB for 4K, <2 GB for 1080p). Current code uses MoviePy which can load entire videos into memory.

**Implementation**:
- Replace MoviePy with direct FFmpeg subprocess pipes for video read/write (via `imageio-ffmpeg` or raw `subprocess`)
- Audio analysis via librosa's streaming load (`librosa.stream()`) for large files
- YOLO inference on one frame at a time (1 FPS keyframe sampling)
- Whisper inference on extracted audio segments (not full audio)
- Export via FFmpeg stream copy where codec matches, or chunked re-encode otherwise

---

## R-011: Flet + PyInstaller Packaging Compatibility

**Decision**: Use Flet's desktop mode with PyInstaller packaging. Flet supports PyInstaller through its `flet pack` command or manual PyInstaller configuration with Flet's data files included.

**Rationale**: The spec requires standalone Windows installer (FR-070) and Flet UI (FR-064). Compatibility between these two is critical.

**Key Considerations**:
- Flet uses a Flutter-based runtime that must be bundled as a data file
- `flet pack` wraps PyInstaller with correct Flet data paths
- Alternatively, manual PyInstaller spec can include Flet's internal web/desktop assets
- Test packaging early in development to catch bundling issues

---

## R-012: Music-Information Dictionary Format and Lookup

**Decision**: Bundled SQLite database file containing normalized music metadata (title, composer, performer/ensemble aliases). Queried locally at runtime — no network access. Curated before release by development team.

**Rationale**: Required by FR-036. SQLite provides efficient lookup for the dictionary while remaining a single bundled file. The dictionary is read-only at runtime, so it doesn't conflict with the JSON-for-state requirement (that applies to mutable application state, not reference data).

**Schema**:
- `works(id, title_normalized, composer_normalized, original_title, original_composer)`
- `performers(id, name_normalized, original_name, ensemble)`
- `work_performers(work_id, performer_id)` — many-to-many
- `dictionary_meta(revision_id, source_summary, generated_at_utc)` — single-row metadata for reproducibility

**Lookup Strategy**: Fuzzy string matching (normalized Levenshtein or trigram similarity) on title and composer fields, used as a secondary signal when transcription confidence is low. The active `revision_id` is carried into mapping/checkpoint context for deterministic replay and auditability.
