# Service Interface Contracts: CVCutter Full Architecture Refactor

**Feature Branch**: `001-codebase-refactor`
**Created**: 2026-03-01
**Layer**: Domain → Infrastructure boundary (Ports)

These are the Protocol-based interfaces defined in `src/cvcutter/domain/services/`. Infrastructure adapters implement these protocols. Domain and application layers depend only on these abstractions.

---

## VideoIOService (`domain/services/video_io.py`)

Abstracts all video/audio file I/O and transcoding operations.

```python
from typing import Protocol, Iterator
from pathlib import Path

class VideoIOService(Protocol):
    """Port for video/audio file operations."""

    def probe(self, file_path: Path) -> VideoProbeResult:
        """Extract metadata (duration, resolution, codec, etc.) from a video/audio file."""
        ...

    def concatenate(self, video_paths: list[Path], output_path: Path) -> Path:
        """Concatenate multiple video files into a single continuous file."""
        ...

    def extract_audio(self, video_path: Path, output_path: Path,
                      sample_rate: int = 22050) -> Path:
        """Extract audio track from video file."""
        ...

    def export_segment(self, source_path: Path, output_path: Path,
                       start_seconds: float, end_seconds: float,
                       audio_mix: AudioMixConfig | None = None,
                       quality: str = "high",
                       use_gpu: bool = False) -> Path:
        """Export a time-range segment with optional audio mixing and GPU acceleration."""
        ...

    def stream_frames(self, video_path: Path, fps: float = 1.0,
                      start_seconds: float = 0.0,
                      end_seconds: float | None = None) -> Iterator[VideoFrame]:
        """Yield video frames at specified FPS for analysis. Memory-efficient streaming."""
        ...

    def check_gpu_available(self) -> bool:
        """Check if GPU hardware acceleration (NVENC) is available."""
        ...

    def get_disk_space(self, path: Path) -> DiskSpaceInfo:
        """Check available disk space at path."""
        ...
```

**Adapter**: `infrastructure/ffmpeg/transcoder.py` — implements via FFmpeg subprocess pipes.

---

## ModelRunnerService (`domain/services/model_runner.py`)

Abstracts ML model inference operations.

```python
from typing import Protocol
from pathlib import Path

class VisualDetectorRunner(Protocol):
    """Port for visual object detection model inference."""

    def detect(self, frame: VideoFrame) -> list[Detection]:
        """Run object detection on a single video frame.
        Returns detected objects with bounding boxes and class labels."""
        ...

    def model_version(self) -> str:
        """Return model identifier and version for checkpoint recording."""
        ...

class SpeechTranscriber(Protocol):
    """Port for speech-to-text transcription."""

    def transcribe(self, audio_path: Path, language: str = "ja") -> TranscriptionResult:
        """Transcribe audio file to text. Returns timestamped segments."""
        ...

    def model_version(self) -> str:
        """Return model identifier and version for checkpoint recording."""
        ...

class AudioContentClassifier(Protocol):
    """Port for audio content type classification."""

    def classify(self, audio_chunk: AudioChunk) -> list[ClassificationResult]:
        """Classify audio content as music/speech/applause/silence.
        Input is a short audio chunk (e.g., 1 second).
        Returns classification probabilities for each content type."""
        ...

    def model_version(self) -> str:
        """Return model identifier and version for checkpoint recording."""
        ...
```

**Adapters**:
- `infrastructure/models/yolo_runner.py` → `VisualDetectorRunner`
- `infrastructure/models/whisper_runner.py` → `SpeechTranscriber`
- `infrastructure/models/audio_classifier_runner.py` → `AudioContentClassifier`

---

## CheckpointStore (`domain/services/checkpoint_store.py`)

Abstracts checkpoint persistence operations.

```python
from typing import Protocol

class CheckpointStore(Protocol):
    """Port for checkpoint read/write operations."""

    def save(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint record."""
        ...

    def load(self, project_id: str, stage: PipelineStage,
             segment_index: int | None = None) -> Checkpoint | None:
        """Load a checkpoint for a specific project and stage.
        Returns None if no checkpoint exists."""
        ...

    def load_all(self, project_id: str) -> list[Checkpoint]:
        """Load all checkpoints for a project, ordered by stage."""
        ...

    def invalidate(self, project_id: str, stage: PipelineStage,
                   segment_index: int | None = None,
                   cascade: bool = True) -> list[str]:
        """Invalidate a checkpoint (optionally for one segment) and optionally all downstream checkpoints.
        Downstream must follow the stage dependency graph (not raw enum order).
        When segment_index is provided, cascade is scoped to downstream checkpoints for that segment;
        global checkpoints are invalidated only when required segment contributions become invalid.
        Returns list of invalidated checkpoint IDs."""
        ...

    def clean_completed(self, project_id: str) -> int:
        """Remove temporary artifacts for completed project.
        Returns count of cleaned files."""
        ...
```

**Adapter**: `infrastructure/persistence/json_checkpoint_store.py`

---

## QuotaStateStore (`domain/services/quota_state_store.py`)

Abstracts persistence for global YouTube quota state.

```python
from typing import Protocol

class QuotaStateStore(Protocol):
    """Port for loading/saving global quota state."""

    def load(self) -> QuotaState | None:
        """Load global quota state from persistence."""
        ...

    def save(self, state: QuotaState) -> None:
        """Persist global quota state."""
        ...
```

**Adapter**: `infrastructure/persistence/json_quota_state_store.py`

---

## PdfTextExtractor (`domain/services/pdf_text_extractor.py`)

Abstracts mandatory local PDF text extraction for program parsing.

```python
from typing import Protocol
from pathlib import Path

class PdfTextExtractor(Protocol):
    """Port for local-first PDF text extraction.
    This is the required baseline path for FR-031; cloud AI is optional enrichment only.
    Returns empty results for unreadable/unsupported PDFs and never blocks mapping workflow."""

    def extract_text_blocks(self, pdf_path: Path) -> list[PdfTextBlock]:
        """Extract ordered text blocks from a program PDF using local tooling.
        Returns [] if extraction fails or no machine-readable text is available."""
        ...
```

**Adapter**: `infrastructure/pdf/local_extractor.py`

---

## MusicLookupService (`domain/services/music_lookup.py`)

Abstracts read-only lookup against the bundled music metadata dictionary.

```python
from typing import Protocol

class MusicLookupService(Protocol):
    """Port for local bundled dictionary lookup (no runtime network access).
    Must degrade gracefully: return [] on lookup failure and never block mapping workflow."""

    def lookup(self, title: str, composer: str | None = None,
               performers: list[str] | None = None) -> list[MusicLookupMatch]:
        """Return scored dictionary matches for mapping support.
        Returns [] when dictionary data is unavailable/corrupted."""
        ...

    def is_available(self) -> bool:
        """Check whether dictionary data is readable and usable."""
        ...

    def dictionary_revision(self) -> str:
        """Return bundled dictionary revision identifier for reproducibility."""
        ...
```

**Adapter**: `infrastructure/music/sqlite_lookup.py`

---

## UploadService (`domain/services/upload_service.py`)

Abstracts video upload operations.

```python
from typing import Protocol, Callable
from pathlib import Path

class UploadService(Protocol):
    """Port for video upload to hosting platform.
    Methods raise UploadError on non-recoverable service failures unless result-type errors are returned."""

    def authenticate(self) -> bool:
        """Authenticate with the upload service. Returns True if successful."""
        ...

    def upload(self, file_path: Path, metadata: UploadMetadata,
               progress_callback: Callable[[int, int], None] | None = None,
               resumable_uri: str | None = None) -> UploadResult:
        """Upload a video file with metadata.
        Supports resumable uploads via resumable_uri.
        progress_callback receives (bytes_uploaded, total_bytes)."""
        ...

    def create_playlist(self, title: str, description: str = "",
                        privacy: PrivacySetting = PrivacySetting.PUBLIC) -> str:
        """Create a playlist. Returns playlist ID.
        Raises UploadError if creation fails."""
        ...

    def add_to_playlist(self, playlist_id: str, video_id: str) -> None:
        """Add a video to a playlist.
        Raises UploadError if playlist assignment fails."""
        ...
```

**Adapter**: `infrastructure/youtube/client.py`

---

## CredentialStore (`domain/services/credential_store.py`)

Abstracts credential read/write with redaction support.

```python
from typing import Protocol

class CredentialStore(Protocol):
    """Port for credential storage and retrieval."""

    def load(self, service_name: str) -> dict[str, str] | None:
        """Load credentials for a named service.
        Returns None if no credentials stored."""
        ...

    def save(self, service_name: str, credentials: dict[str, str]) -> None:
        """Save credentials for a named service.
        Must set per-user file permissions on storage."""
        ...

    def delete(self, service_name: str) -> None:
        """Delete stored credentials for a named service."""
        ...

    def redacted_summary(self, service_name: str) -> dict[str, str]:
        """Return credential keys with redacted values for display/logging."""
        ...
```

**Adapter**: `infrastructure/persistence/json_credential_store.py`

---

## FormDataService (`domain/services/form_data_service.py`)

Abstracts form-response ingestion from local CSV and Google APIs.

```python
from typing import Protocol
from pathlib import Path

class FormDataService(Protocol):
    """Port for form-response loading.
    Must support deterministic local CSV ingestion and optional API-backed retrieval."""

    def load_csv(self, csv_path: Path) -> list[FormResponse]:
        """Load form responses from a local CSV file."""
        ...

    def fetch_remote(self, form_id: str | None = None,
                     sheet_id: str | None = None) -> list[FormResponse]:
        """Fetch form responses from Google Forms/Sheets APIs.
        Raises ConfigurationError when API access is not configured."""
        ...
```

**Adapters**:
- `infrastructure/forms/form_data_service.py` (composite adapter implementing this protocol)
- `infrastructure/csv/form_csv_loader.py` (local CSV ingestion component)
- `infrastructure/google/forms_client.py` (remote fetch component)
- `infrastructure/google/sheets_client.py` (remote fetch component)

---

## AIEnrichmentService (`domain/services/ai_enrichment.py`)

Abstracts optional cloud AI enrichment (failure-aware, manually overridable).

```python
from typing import Protocol
from pathlib import Path

class AIEnrichmentService(Protocol):
    """Port for optional cloud AI enrichment.
    All methods MUST be failure-aware: return None/empty on failure, never raise."""

    def parse_pdf(self, pdf_path: Path,
                  local_entries: list[ProgramEntry]) -> list[ProgramEntry] | None:
        """Optionally enrich local PDF parsing results using cloud AI.
        Local parsing remains the required baseline; returns None if service unavailable."""
        ...

    def match_form_responses(self, segments: list[PerformanceSegment],
                              entries: list[ProgramEntry],
                              responses: list[FormResponse]) -> list[SuggestedMapping] | None:
        """Suggest segment-to-metadata mappings (including form-response links) using cloud AI.
        Suggestions are keyed by stable entity IDs, not list positions.
        Returns None if service unavailable."""
        ...

    def is_available(self) -> bool:
        """Check if the cloud AI service is currently accessible."""
        ...
```

**Adapter**: `infrastructure/gemini/client.py`

---

## Data Transfer Types

These types are used across service interfaces and are defined in
`src/cvcutter/domain/services/types.py`:

```python
@dataclass(frozen=True)
class VideoProbeResult:
    duration_seconds: float
    resolution: tuple[int, int]
    codec: str
    frame_rate: float
    file_size_bytes: int
    has_audio: bool

@dataclass(frozen=True)
class VideoFrame:
    data: np.ndarray        # Frame pixel data (H, W, C)
    timestamp_seconds: float
    frame_index: int

@dataclass(frozen=True)
class AudioChunk:
    data: np.ndarray        # Audio samples
    sample_rate: int
    start_seconds: float
    duration_seconds: float

@dataclass(frozen=True)
class PdfTextBlock:
    text: str
    page_number: int
    block_index: int

@dataclass(frozen=True)
class AudioMixConfig:
    video_volume: float     # 0.0–2.0
    mic_volume: float       # 0.0–2.0
    mic_audio_path: Path | None
    sync_offset_seconds: float

@dataclass(frozen=True)
class Detection:
    class_name: str         # e.g., "person", "guitar", "piano"
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 normalized

@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    segments: list[TranscriptionSegment]
    language: str
    confidence: float

@dataclass(frozen=True)
class TranscriptionSegment:
    text: str
    start_seconds: float
    end_seconds: float
    confidence: float

@dataclass(frozen=True)
class ClassificationResult:
    label: str              # "music", "speech", "applause", "silence"
    confidence: float
    start_seconds: float
    end_seconds: float

@dataclass(frozen=True)
class UploadMetadata:
    title: str
    description: str
    tags: list[str]
    privacy_status: PrivacySetting
    category_id: str        # YouTube category (e.g., "10" for Music)
    playlist_id: str | None

@dataclass(frozen=True)
class UploadResult:
    success: bool
    video_id: str | None
    resumable_uri: str | None
    bytes_uploaded: int
    error_message: str | None

@dataclass(frozen=True)
class DiskSpaceInfo:
    total_bytes: int
    free_bytes: int
    path: Path

@dataclass(frozen=True)
class SuggestedMapping:
    segment_id: str
    program_entry_id: str | None
    form_response_id: str | None
    confidence: float
    reason: str

@dataclass(frozen=True)
class MusicLookupMatch:
    work_id: str
    title: str
    composer: str | None
    performers: list[str]
    score: float
    dictionary_revision: str
```
