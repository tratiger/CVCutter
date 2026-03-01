# Quickstart: CVCutter Full Architecture Refactor

**Feature Branch**: `001-codebase-refactor`
**Created**: 2026-03-01

## Prerequisites

- Python ≥3.11 (development uses 3.13)
- [uv](https://docs.astral.sh/uv/) installed
- FFmpeg available on PATH (or installed via system package manager)
- NVIDIA GPU with NVENC support (optional, for GPU-accelerated processing)
- Windows 10/11 (primary target)

## Setup

```powershell
# Clone and enter repository
git clone <repo-url> CVCutter
cd CVCutter
git checkout 001-codebase-refactor

# Install dependencies (uv manages the virtual environment)
uv sync

# Verify installation
uv run python -c "import cvcutter; print('cvcutter import ok')"
```

## Development Commands

```powershell
# Run the application
uv run cvcutter

# Run full test suite with coverage
uv run pytest --cov=src/cvcutter --cov-report=term-missing

# Run specific test categories
uv run pytest tests/unit/                    # Unit tests only
uv run pytest tests/integration/             # Integration tests only
uv run pytest tests/contract/                # Contract tests only
uv run pytest tests/unit/domain/             # Domain unit tests only

# Static type checking
uv run pyright

# Lint checking
uv run ruff check .

# Auto-fix lint issues
uv run ruff check . --fix

# Run all quality gates (must pass before merge)
uv run ruff check . && uv run pyright && uv run pytest --cov=src/cvcutter --cov-report=term-missing
```

## Project Structure Overview

```text
src/cvcutter/
├── domain/           # Pure business logic (no infrastructure/UI/service SDK imports)
│   ├── models/       # Data entities (Project, Segment, Checkpoint, etc.)
│   ├── detection/    # Performance segment detection algorithms
│   ├── audio/        # Audio synchronization logic
│   ├── mapping/      # Video-to-metadata matching logic
│   └── services/     # Protocol interfaces (ports)
├── application/      # Orchestration layer
├── infrastructure/   # External system adapters (FFmpeg, YouTube, models)
├── presentation/     # Flet UI (views + view-models)
└── shared/           # Cross-cutting utilities

tests/
├── unit/             # Fast, isolated tests (no I/O, no network)
├── integration/      # Cross-module workflow tests
└── contract/         # External adapter contract tests
```

## Architecture Rules

1. **Domain is king**: `domain/` has ZERO imports from `infrastructure/`, `presentation/`, or external service SDKs (scientific runtime libs like `numpy` are allowed).
2. **Protocols, not inheritance**: Cross-layer boundaries use `typing.Protocol` (structural subtyping).
3. **Application orchestrates**: `application/` coordinates domain logic + infrastructure adapters.
4. **Infrastructure adapts**: `infrastructure/` implements domain protocols for external systems.
5. **Presentation binds**: `presentation/` uses view-models that call application services.

## Key Workflows

### Processing a Concert

1. **Load**: Select video files, optional mic audio, program PDF, form CSV
2. **Process**: Pipeline runs: concatenate → detect segments → sync audio → prepare `READY_FOR_EXPORT`
3. **Preview/Map**: Review/adjust boundaries, export segments, then auto-match metadata with manual correction
4. **Upload**: Batch upload to YouTube with metadata; quota management handles limits

### Checkpoint/Resume

- Checkpoints are saved after each major stage, plus per-segment checkpoints for EXPORT and UPLOAD (JSON in app config directory)
- On resume: input hashes + config + model versions are validated
- Invalid checkpoints cascade: invalidating detection also invalidates export/mapping/upload
- User can choose: resume from checkpoint OR restart from scratch

## Configuration

Application config is stored as JSON in the per-user app data directory:
- Windows: `%LOCALAPPDATA%/cvcutter/config.json`

Key settings:
- `enable_yolo_detection`: Toggle YOLO visual detection (disable for low-spec PCs)
- `enable_gpu`: Toggle GPU acceleration
- `enable_gemini`: Toggle optional cloud AI enrichment
- Audio mix volumes, output format/quality, minimum segment duration

## Building the Installer

```powershell
# Build standalone Windows executable (developer validation artifact)
uv run python build_exe.py

# Output: dist/CVCutter.exe (or dist/CVCutter/ for directory mode)
# Release installer packaging wraps this dist output into a Windows installer artifact.
```

The release installer bundles:
- Python runtime + all dependencies
- YOLOv8n model (~6 MB)
- Whisper small model (~461 MB)
- Audio content classifier (~50 MB)
- Flet runtime assets

## Testing Strategy

| Category | Scope | Coverage Target |
|----------|-------|----------------|
| Unit (domain) | Detection, sync, mapping, models | ≥90% |
| Unit (application) | Pipeline, workflows, checkpoint logic | ≥80% |
| Unit (infrastructure) | Adapter implementations | ≥80% |
| Integration | Cross-module pipelines | Key workflows |
| Contract | External API adapters | API compatibility |

## Troubleshooting

- **FFmpeg not found**: Ensure `ffmpeg` is on PATH. Install via `winget install FFmpeg` or download from ffmpeg.org.
- **CUDA/GPU errors**: Set `enable_gpu: false` in settings. GPU is optional.
- **Model loading failures**: Ensure bundled model files exist in the expected local paths for your environment. No runtime first-use model download path is supported.
- **Import errors**: Run `uv sync` to ensure all dependencies are installed.
