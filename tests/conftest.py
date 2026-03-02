"""Shared test fixtures for CVCutter test suite.

Provides factories, stubs, and fixtures used across unit, integration,
contract, and security tests.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest


# ──────────────────────────────────────────────────────
# Fixture: Temporary project directory
# ──────────────────────────────────────────────────────


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory structure."""
    project_id = str(uuid.uuid4())
    project_dir = tmp_path / "cvcutter" / "projects" / project_id
    project_dir.mkdir(parents=True)
    (project_dir / "checkpoints").mkdir()
    return project_dir


@pytest.fixture
def tmp_app_dir(tmp_path: Path) -> Path:
    """Create a temporary app config directory mimicking LOCALAPPDATA/cvcutter."""
    app_dir = tmp_path / "cvcutter"
    app_dir.mkdir(parents=True)
    (app_dir / "projects").mkdir()
    (app_dir / "credentials").mkdir()
    (app_dir / "logs").mkdir()
    (app_dir / "reference").mkdir()
    return app_dir


# ──────────────────────────────────────────────────────
# Factory helpers
# ──────────────────────────────────────────────────────


def make_project_id() -> str:
    """Generate a new project UUID."""
    return str(uuid.uuid4())


def make_project_config(**overrides: Any) -> dict[str, Any]:
    """Create a ProjectConfig-compatible dict with sensible defaults."""
    defaults: dict[str, Any] = {
        "video_audio_volume": 0.6,
        "mic_audio_volume": 1.5,
        "audio_sync_sample_rate": 22050,
        "enable_yolo_detection": True,
        "min_segment_duration_seconds": 30.0,
        "output_format": "mp4",
        "output_quality": "high",
        "enable_gpu": True,
        "enable_gemini": True,
        "gemini_model": "gemini-2.5-flash",
        "youtube_chunk_size": 5242880,
        "mapping_review_threshold": 0.8,
    }
    defaults.update(overrides)
    return defaults


def make_segment_dict(
    *,
    segment_index: int = 0,
    start_time: float = 0.0,
    end_time: float = 120.0,
    confidence: float = 0.85,
    detection_mode: str = "full",
) -> dict[str, Any]:
    """Create a PerformanceSegment-compatible dict."""
    return {
        "id": str(uuid.uuid4()),
        "segment_index": segment_index,
        "start_time_seconds": start_time,
        "end_time_seconds": end_time,
        "detection_confidence": confidence,
        "effective_detection_mode": detection_mode,
        "detection_signals": [],
        "fallback_reason": None if detection_mode == "full" else "TOGGLE_DISABLED",
        "exported_file_path": None,
        "export_status": "NOT_EXPORTED",
        "user_adjusted": False,
    }


def make_checkpoint_dict(
    *,
    project_id: str = "",
    stage: str = "DETECTION",
    status: str = "VALID",
    input_hashes: dict[str, str] | None = None,
    config_snapshot: dict[str, Any] | None = None,
    model_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a Checkpoint-compatible dict."""
    return {
        "id": str(uuid.uuid4()),
        "project_id": project_id or make_project_id(),
        "stage": stage,
        "status": status,
        "created_at": datetime.now(UTC).isoformat(),
        "input_hashes": input_hashes or {"video.mp4": "abc123"},
        "config_snapshot": config_snapshot or make_project_config(),
        "model_versions": model_versions or {"yolov8n": "v8.0.0"},
        "output_references": [],
        "segment_index": None,
        "error_detail": None,
    }


def make_upload_record_dict(
    *,
    segment_id: str = "",
    mapping_id: str = "",
    status: str = "PENDING",
) -> dict[str, Any]:
    """Create an UploadRecord-compatible dict."""
    return {
        "id": str(uuid.uuid4()),
        "segment_id": segment_id or str(uuid.uuid4()),
        "mapping_id": mapping_id or str(uuid.uuid4()),
        "youtube_video_id": None,
        "upload_status": status,
        "privacy_setting": "PUBLIC",
        "playlist_id": None,
        "quota_cost": 1600,
        "retry_count": 0,
        "error_detail": None,
        "resumable_upload_uri": None,
        "bytes_uploaded": 0,
        "failure_kind": None,
        "session_invalidated_at_utc": None,
        "restart_from_zero": False,
        "youtube_url": None,
        "uploaded_at": None,
    }


# ──────────────────────────────────────────────────────
# Stub video file helpers
# ──────────────────────────────────────────────────────


@pytest.fixture
def stub_video_file(tmp_path: Path) -> Path:
    """Create a minimal stub file pretending to be a video."""
    video = tmp_path / "test_video.mp4"
    video.write_bytes(b"\x00" * 1024)  # 1KB stub
    return video


@pytest.fixture
def stub_audio_file(tmp_path: Path) -> Path:
    """Create a minimal stub file pretending to be audio."""
    audio = tmp_path / "test_audio.wav"
    audio.write_bytes(b"\x00" * 512)
    return audio


@pytest.fixture
def stub_pdf_file(tmp_path: Path) -> Path:
    """Create a minimal stub file pretending to be a PDF."""
    pdf = tmp_path / "program.pdf"
    pdf.write_bytes(b"%PDF-1.4 stub")
    return pdf


@pytest.fixture
def stub_csv_file(tmp_path: Path) -> Path:
    """Create a minimal stub CSV with form response data."""
    csv = tmp_path / "responses.csv"
    csv.write_text(
        "performer_name,piece_title,privacy_preference\n"
        "田中太郎,交響曲第5番,PUBLIC\n"
        "鈴木花子,月光ソナタ,UNLISTED\n",
        encoding="utf-8",
    )
    return csv


# ──────────────────────────────────────────────────────
# JSON persistence helpers
# ──────────────────────────────────────────────────────


def write_json(path: Path, data: Any) -> None:
    """Write JSON data to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def read_json(path: Path) -> Any:
    """Read JSON data from file."""
    return json.loads(path.read_text(encoding="utf-8"))
