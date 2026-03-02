"""Protocol contract for video and audio I/O operations.

Infrastructure adapters implement this port to provide probing, transcoding,
frame streaming, and disk-capacity checks without leaking adapter details.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from cvcutter.domain.services.types import (
        AudioChunk,
        AudioMixConfig,
        DiskSpaceInfo,
        VideoFrame,
        VideoProbeResult,
    )


@runtime_checkable
class VideoIOService(Protocol):
    """Port for video/audio file operations."""

    def probe(self, file_path: Path) -> VideoProbeResult:
        """Extract metadata (duration, resolution, codec, and related details)."""
        ...

    def concatenate(
        self,
        video_paths: list[Path],
        output_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Concatenate videos into a single file and report bytes progress when provided."""
        ...

    def extract_audio(self, video_path: Path, output_path: Path, sample_rate: int = 22050) -> Path:
        """Extract an audio track from a video file at the requested sample rate."""
        ...

    def export_segment(
        self,
        source_path: Path,
        output_path: Path,
        start_seconds: float,
        end_seconds: float,
        audio_mix: AudioMixConfig | None = None,
        quality: str = "high",
        use_gpu: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Export a bounded segment with optional audio mixing and progress callbacks."""
        ...

    def stream_frames(
        self,
        video_path: Path,
        fps: float = 1.0,
        start_seconds: float = 0.0,
        end_seconds: float | None = None,
    ) -> Iterator[VideoFrame]:
        """Yield analysis frames at a target frame-rate using memory-efficient streaming."""
        ...

    def stream_audio_chunks(
        self,
        video_path: Path,
        sample_rate: int = 22050,
        chunk_seconds: float = 1.0,
        start_seconds: float = 0.0,
        end_seconds: float | None = None,
    ) -> Iterator[AudioChunk]:
        """Yield mono PCM audio chunks using streaming pipe reads."""
        ...

    def check_gpu_available(self) -> bool:
        """Check if GPU hardware acceleration is available for export workloads."""
        ...

    def get_disk_space(self, path: Path) -> DiskSpaceInfo:
        """Return total and free disk-space information for the given path."""
        ...

