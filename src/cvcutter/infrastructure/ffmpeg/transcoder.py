"""FFmpeg-based implementation of the video/audio I/O domain service."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import imageio_ffmpeg
import numpy as np

from cvcutter.domain.services.types import (
    AudioChunk,
    AudioMixConfig,
    DiskSpaceInfo,
    VideoFrame,
    VideoProbeResult,
)
from cvcutter.domain.services.video_io import VideoIOService
from cvcutter.infrastructure.ffmpeg.gpu_detect import detect_nvenc

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_SUPPORTED_QUALITY = {"low", "medium", "high"}


def _resolve_ffprobe_executable(ffmpeg_executable: str) -> str:
    """Resolve an ffprobe executable path adjacent to the ffmpeg binary."""
    ffmpeg_path = Path(ffmpeg_executable)
    probe_name = "ffprobe.exe" if ffmpeg_path.suffix.lower() == ".exe" else "ffprobe"
    candidate = ffmpeg_path.with_name(probe_name)
    return str(candidate) if candidate.exists() else "ffprobe"


def _parse_fraction(value: str | None) -> float:
    """Parse `num/den` or numeric string values safely into a float."""
    if not value or value in {"N/A", "0/0"}:
        return 0.0
    try:
        if "/" in value:
            numerator_text, denominator_text = value.split("/", maxsplit=1)
            denominator = float(denominator_text)
            if denominator == 0:
                return 0.0
            return float(numerator_text) / denominator
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_float(value: Any) -> float:
    """Parse scalar numeric metadata safely into float values."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_int(value: Any, fallback: int = 0) -> int:
    """Parse integer metadata safely with fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


class FFmpegTranscoder(VideoIOService):
    """Adapter that performs probing/transcoding via FFmpeg and ffprobe."""

    def __init__(self, ffmpeg_executable: str | None = None) -> None:
        """Initialize the adapter using imageio-ffmpeg executable discovery."""
        self._ffmpeg_executable = ffmpeg_executable or imageio_ffmpeg.get_ffmpeg_exe()
        self._ffprobe_executable = _resolve_ffprobe_executable(self._ffmpeg_executable)

    def _run_command(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """Execute an external command and raise RuntimeError on failure."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
            )
        except OSError as exc:
            raise RuntimeError(f"Unable to execute command: {' '.join(command)}") from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown command failure"
            raise RuntimeError(f"Command failed ({' '.join(command)}): {detail}")
        return result

    def probe(self, file_path: Path) -> VideoProbeResult:
        """Probe media metadata using ffprobe JSON output."""
        target = Path(file_path)
        if not target.exists():
            raise FileNotFoundError(f"Media file does not exist: {target}")

        command = [
            self._ffprobe_executable,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(target),
        ]
        result = self._run_command(command)

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("ffprobe returned invalid JSON output.") from exc

        streams = payload.get("streams", [])
        format_info = payload.get("format", {})
        if not isinstance(streams, list):
            streams = []
        if not isinstance(format_info, dict):
            format_info = {}

        video_stream = next(
            (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
            {},
        )
        has_audio = any(
            isinstance(stream, dict) and stream.get("codec_type") == "audio"
            for stream in streams
        )

        duration_seconds = _parse_float(format_info.get("duration"))
        if duration_seconds <= 0:
            duration_seconds = _parse_float(video_stream.get("duration"))
        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        codec = str(video_stream.get("codec_name") or "")
        frame_rate = _parse_fraction(
            str(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/0"),
        )
        file_size_bytes = _parse_int(format_info.get("size"), target.stat().st_size)

        return VideoProbeResult(
            duration_seconds=duration_seconds,
            resolution=(width, height),
            codec=codec,
            frame_rate=frame_rate,
            file_size_bytes=file_size_bytes,
            has_audio=has_audio,
        )

    def concatenate(
        self,
        video_paths: list[Path],
        output_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Concatenate videos via FFmpeg concat demuxer."""
        if not video_paths:
            raise ValueError("video_paths must not be empty.")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        validated_paths = [Path(path) for path in video_paths]
        for source in validated_paths:
            if not source.exists():
                raise FileNotFoundError(f"Input video file does not exist: {source}")

        if len(validated_paths) == 1:
            shutil.copy2(validated_paths[0], output)
            if progress_callback is not None:
                copied_size = output.stat().st_size
                progress_callback(copied_size, copied_size)
            return output

        total_bytes = sum(path.stat().st_size for path in validated_paths)
        if progress_callback is not None:
            progress_callback(0, total_bytes)

        list_file_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".txt",
                delete=False,
            ) as list_file:
                list_file_path = Path(list_file.name)
                for source in validated_paths:
                    escaped = str(source.resolve()).replace("'", "'\\''")
                    list_file.write(f"file '{escaped}'\n")

            command = [
                self._ffmpeg_executable,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file_path),
                "-c",
                "copy",
                str(output),
            ]
            self._run_command(command)
        finally:
            if list_file_path is not None and list_file_path.exists():
                list_file_path.unlink()

        if progress_callback is not None:
            output_size = output.stat().st_size if output.exists() else total_bytes
            total = max(total_bytes, output_size)
            progress_callback(output_size, total)
        return output

    def extract_audio(self, video_path: Path, output_path: Path, sample_rate: int = 22050) -> Path:
        """Extract the primary audio track from a video file."""
        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero.")

        source = Path(video_path)
        if not source.exists():
            raise FileNotFoundError(f"Video file does not exist: {source}")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        command = [
            self._ffmpeg_executable,
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            str(output),
        ]
        self._run_command(command)
        return output

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
        """Export a segment with optional mixed microphone audio and optional NVENC."""
        if start_seconds < 0:
            raise ValueError("start_seconds must be >= 0.")
        if end_seconds <= start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds.")

        quality_mode = quality.lower().strip()
        if quality_mode not in _SUPPORTED_QUALITY:
            raise ValueError(f"quality must be one of {sorted(_SUPPORTED_QUALITY)}.")

        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source video file does not exist: {source}")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback is not None:
            total_hint = max(1, source.stat().st_size)
            progress_callback(0, total_hint)

        command = [
            self._ffmpeg_executable,
            "-y",
            "-ss",
            f"{start_seconds:.6f}",
            "-to",
            f"{end_seconds:.6f}",
            "-i",
            str(source),
        ]

        if audio_mix is not None and audio_mix.mic_audio_path is not None:
            mic_audio_path = Path(audio_mix.mic_audio_path)
            if not mic_audio_path.exists():
                raise FileNotFoundError(f"Mic audio file does not exist: {mic_audio_path}")

            source_has_audio = True
            try:
                source_has_audio = self.probe(source).has_audio
            except Exception:
                source_has_audio = True

            command.extend(
                [
                    "-itsoffset",
                    f"{audio_mix.sync_offset_seconds:.6f}",
                    "-i",
                    str(mic_audio_path),
                ],
            )
            if source_has_audio:
                command.extend(
                    [
                        "-filter_complex",
                        (
                            f"[0:a]volume={audio_mix.video_volume}[a0];"
                            f"[1:a]volume={audio_mix.mic_volume}[a1];"
                            "[a0][a1]amix=inputs=2:duration=first[aout]"
                        ),
                        "-map",
                        "0:v",
                        "-map",
                        "[aout]",
                    ],
                )
            elif abs(audio_mix.mic_volume - 1.0) > 1e-6:
                command.extend(
                    [
                        "-filter_complex",
                        f"[1:a]volume={audio_mix.mic_volume}[aout]",
                        "-map",
                        "0:v",
                        "-map",
                        "[aout]",
                    ],
                )
            else:
                command.extend(["-map", "0:v", "-map", "1:a"])
        else:
            command.extend(["-map", "0:v", "-map", "0:a?"])

        if use_gpu and self.check_gpu_available():
            gpu_presets = {"low": "p1", "medium": "p4", "high": "p6"}
            command.extend(["-c:v", "h264_nvenc", "-preset", gpu_presets[quality_mode]])
        else:
            cpu_presets = {"low": "veryfast", "medium": "medium", "high": "slow"}
            crf_values = {"low": "28", "medium": "23", "high": "19"}
            command.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    cpu_presets[quality_mode],
                    "-crf",
                    crf_values[quality_mode],
                ],
            )

        command.extend(["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)])
        self._run_command(command)

        if progress_callback is not None:
            output_size = output.stat().st_size if output.exists() else 0
            total = max(output_size, source.stat().st_size)
            progress_callback(output_size, total)
        return output

    def stream_frames(
        self,
        video_path: Path,
        fps: float = 1.0,
        start_seconds: float = 0.0,
        end_seconds: float | None = None,
    ) -> Iterator[VideoFrame]:
        """Yield RGB frames using imageio-ffmpeg's pipe reader."""
        if fps <= 0:
            raise ValueError("fps must be greater than zero.")
        if start_seconds < 0:
            raise ValueError("start_seconds must be >= 0.")
        if end_seconds is not None and end_seconds <= start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds when provided.")

        source = Path(video_path)
        if not source.exists():
            raise FileNotFoundError(f"Video file does not exist: {source}")

        input_params = ["-ss", f"{start_seconds:.6f}"]
        if end_seconds is not None:
            input_params.extend(["-to", f"{end_seconds:.6f}"])
        output_params = ["-vf", f"fps={fps}"]

        reader: Any = None
        try:
            reader = imageio_ffmpeg.read_frames(
                str(source),
                pix_fmt="rgb24",
                input_params=input_params,
                output_params=output_params,
            )
            metadata = next(reader)
            if not isinstance(metadata, dict):
                raise RuntimeError("Frame stream did not return metadata.")

            size = metadata.get("size") or metadata.get("source_size")
            if not isinstance(size, (list, tuple)) or len(size) != 2:
                raise RuntimeError("Unable to determine frame size from stream metadata.")

            width = int(size[0])
            height = int(size[1])
            frame_size_bytes = width * height * 3

            for frame_index, frame_bytes in enumerate(reader):
                if len(frame_bytes) != frame_size_bytes:
                    continue
                timestamp = start_seconds + (frame_index / fps)
                if end_seconds is not None and timestamp >= end_seconds:
                    break

                frame_data = np.frombuffer(frame_bytes, dtype=np.uint8).reshape((height, width, 3))
                yield VideoFrame(
                    data=frame_data.copy(),
                    timestamp_seconds=timestamp,
                    frame_index=frame_index,
                )
        except Exception as exc:
            raise RuntimeError(f"Failed to stream frames from {source}.") from exc
        finally:
            close = getattr(reader, "close", None)
            if callable(close):
                close()

    def stream_audio_chunks(
        self,
        video_path: Path,
        sample_rate: int = 22050,
        chunk_seconds: float = 1.0,
        start_seconds: float = 0.0,
        end_seconds: float | None = None,
    ) -> Iterator[AudioChunk]:
        """Yield mono PCM audio chunks from FFmpeg stdout pipe without full-memory loading."""
        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero.")
        if chunk_seconds <= 0:
            raise ValueError("chunk_seconds must be greater than zero.")
        if start_seconds < 0:
            raise ValueError("start_seconds must be >= 0.")
        if end_seconds is not None and end_seconds <= start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds when provided.")

        source = Path(video_path)
        if not source.exists():
            raise FileNotFoundError(f"Video file does not exist: {source}")

        samples_per_chunk = max(1, int(sample_rate * chunk_seconds))
        bytes_per_sample = 2  # s16le
        chunk_size_bytes = samples_per_chunk * bytes_per_sample

        command = [
            self._ffmpeg_executable,
            "-v",
            "error",
            "-ss",
            f"{start_seconds:.6f}",
        ]
        if end_seconds is not None:
            command.extend(["-to", f"{end_seconds:.6f}"])
        command.extend(["-i", str(source)])
        command.extend(
            [
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-f",
                "s16le",
                "pipe:1",
            ],
        )

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise RuntimeError(f"Unable to execute command: {' '.join(command)}") from exc

        if process.stdout is None:
            process.kill()
            raise RuntimeError("FFmpeg audio stream failed to initialize stdout pipe.")

        chunk_index = 0
        stderr_output = ""
        expected_termination = False
        active_exception: BaseException | None = None
        try:
            while True:
                chunk_bytes = process.stdout.read(chunk_size_bytes)
                if not chunk_bytes:
                    break

                valid_length = len(chunk_bytes) - (len(chunk_bytes) % bytes_per_sample)
                if valid_length <= 0:
                    continue
                pcm = np.frombuffer(chunk_bytes[:valid_length], dtype=np.int16).astype(np.float32) / 32768.0
                timestamp = start_seconds + (chunk_index * chunk_seconds)
                duration_seconds = len(pcm) / sample_rate
                if end_seconds is not None and timestamp >= end_seconds:
                    break
                yield AudioChunk(
                    data=pcm.copy(),
                    sample_rate=sample_rate,
                    start_seconds=timestamp,
                    duration_seconds=duration_seconds,
                )
                chunk_index += 1
        except GeneratorExit as exc:
            expected_termination = True
            active_exception = exc
            raise
        except Exception as exc:
            active_exception = exc
            raise
        finally:
            close_stdout = getattr(process.stdout, "close", None)
            if callable(close_stdout):
                close_stdout()
            if process.stderr is not None:
                stderr_output = process.stderr.read().decode("utf-8", errors="replace")
                process.stderr.close()
            return_code = process.wait()
            if return_code != 0 and not expected_termination and active_exception is None:
                detail = stderr_output.strip() or "unknown command failure"
                raise RuntimeError(f"Command failed ({' '.join(command)}): {detail}")

    def check_gpu_available(self) -> bool:
        """Return True if FFmpeg exposes NVENC hardware encoding support."""
        return detect_nvenc()

    def get_disk_space(self, path: Path) -> DiskSpaceInfo:
        """Return disk-space snapshot for the given filesystem path."""
        target_path = Path(path)
        usage = shutil.disk_usage(target_path)
        return DiskSpaceInfo(total_bytes=usage.total, free_bytes=usage.free, path=target_path)

