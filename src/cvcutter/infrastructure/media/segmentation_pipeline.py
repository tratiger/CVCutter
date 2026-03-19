from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

def detect_acceleration(capabilities: set[str]) -> bool:
    if "gpu" not in capabilities:
        return False
    if not hasattr(cv2, "cuda"):
        return False
    try:
        return cv2.cuda.getCudaEnabledDeviceCount() > 0
    except cv2.error:
        return False


def _to_grayscale(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame
    if frame.ndim == 3:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    raise ValueError("frame must be 2D or 3D image array")


def _fill_short_gaps(flags: list[bool], max_gap: int) -> list[bool]:
    if max_gap <= 0:
        return flags
    fixed = flags[:]
    gap_start: int | None = None
    for index, value in enumerate(flags):
        if value and gap_start is not None:
            gap_length = index - gap_start
            if gap_length <= max_gap and gap_start > 0:
                if flags[gap_start - 1]:
                    for gap_index in range(gap_start, index):
                        fixed[gap_index] = True
            gap_start = None
        elif not value and gap_start is None:
            gap_start = index
    return fixed


def segment_stream(
    frames: Sequence[np.ndarray],
    acceleration: bool,
    motion_ratio_threshold: float = 0.02,
    min_segment_length: int = 5,
    max_gap_frames: int = 2,
) -> list[tuple[int, int]]:
    if not frames:
        return []
    var_threshold = 32 if acceleration else 16
    history = 90 if acceleration else 120
    subtractor = cv2.createBackgroundSubtractorMOG2(
        history=history,
        varThreshold=var_threshold,
        detectShadows=False,
    )
    motion_flags: list[bool] = []
    previous_gray: np.ndarray | None = None
    for frame in frames:
        grayscale = _to_grayscale(np.asarray(frame, dtype=np.uint8))
        mask = subtractor.apply(grayscale)
        _, binary_mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        motion_ratio = float(np.count_nonzero(binary_mask)) / float(binary_mask.size)
        frame_diff_ratio = 0.0
        if previous_gray is not None:
            diff = cv2.absdiff(grayscale, previous_gray)
            _, diff_binary = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            frame_diff_ratio = float(np.count_nonzero(diff_binary)) / float(diff_binary.size)
        previous_gray = grayscale
        is_motion = max(motion_ratio, frame_diff_ratio) >= motion_ratio_threshold
        motion_flags.append(is_motion)

    smoothed_flags = _fill_short_gaps(motion_flags, max_gap=max_gap_frames)
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for index, is_motion in enumerate(smoothed_flags):
        if is_motion and start is None:
            start = index
        elif not is_motion and start is not None:
            if index - start >= min_segment_length:
                segments.append((start, index - 1))
            start = None
    if start is not None and len(smoothed_flags) - start >= min_segment_length:
        segments.append((start, len(smoothed_flags) - 1))
    return segments
