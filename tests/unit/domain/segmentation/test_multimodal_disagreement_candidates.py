from __future__ import annotations

import numpy as np

from cvcutter.domain.segmentation.boundary_aggregator import aggregate_boundaries
from cvcutter.infrastructure.media.segmentation_pipeline import segment_stream


def test_multimodal_boundary_aggregation() -> None:
    value = aggregate_boundaries([(10.0, 0.2), (20.0, 0.8)])
    assert 17 <= value <= 19


def _frame_with_square(offset: int, size: int = 64) -> np.ndarray:
    frame = np.zeros((size, size, 3), dtype=np.uint8)
    start = max(0, min(size - 16, offset))
    frame[16:32, start : start + 16] = 255
    return frame


def _build_dummy_performance_frames() -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    frames.extend(np.zeros((64, 64, 3), dtype=np.uint8) for _ in range(10))
    frames.extend(_frame_with_square(offset) for offset in range(0, 30, 2))
    frames.extend(np.zeros((64, 64, 3), dtype=np.uint8) for _ in range(10))
    frames.extend(_frame_with_square(offset) for offset in range(24, -2, -2))
    return frames


def test_segment_stream_detects_two_motion_regions_from_dummy_frames() -> None:
    frames = _build_dummy_performance_frames()
    segments = segment_stream(
        frames=frames,
        acceleration=False,
        motion_ratio_threshold=0.01,
        min_segment_length=4,
    )
    assert len(segments) == 2
    first, second = segments
    assert 8 <= first[0] <= 13
    assert 20 <= first[1] <= 27
    assert 30 <= second[0] <= 37
    assert 42 <= second[1] <= 49
