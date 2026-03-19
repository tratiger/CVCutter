import pytest

from cvcutter.application.services.synchronization_service import choose_sync_path, estimate_offset_ms


def test_single_source_path() -> None:
    assert choose_sync_path(1, has_embedded_video_audio=True) == "auto_skip"


def test_single_external_source_requires_manual_sync() -> None:
    assert choose_sync_path(1, has_embedded_video_audio=False) == "manual_sync"


def test_invalid_audio_source_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        choose_sync_path(0)


def test_estimate_offset_ms_detects_positive_lag() -> None:
    reference = [0.0, 1.0, 0.0, 0.0]
    target = [0.0, 0.0, 1.0, 0.0]
    offset = estimate_offset_ms(reference, target, sample_rate=1000)
    assert offset > 0


def test_estimate_offset_ms_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        estimate_offset_ms([], [1.0], sample_rate=1000)
    with pytest.raises(ValueError):
        estimate_offset_ms([1.0], [], sample_rate=1000)
    with pytest.raises(ValueError):
        estimate_offset_ms([1.0], [1.0], sample_rate=0)
    with pytest.raises(ValueError):
        estimate_offset_ms([1.0, float("nan")], [1.0, 2.0], sample_rate=1000)
    with pytest.raises(ValueError):
        estimate_offset_ms([1.0, 2.0], [1.0, float("inf")], sample_rate=1000)


def test_estimate_offset_ms_returns_zero_for_flat_signals() -> None:
    offset = estimate_offset_ms([1.0, 1.0, 1.0], [2.0, 2.0, 2.0], sample_rate=1000)
    assert offset == 0


def test_estimate_offset_ms_fft_path_matches_expected_lag() -> None:
    reference = [0.0, 0.0, 1.0, 0.0, 0.0]
    target = [0.0, 0.0, 0.0, 1.0, 0.0]
    offset = estimate_offset_ms(reference, target, sample_rate=1000)
    assert offset == 1
