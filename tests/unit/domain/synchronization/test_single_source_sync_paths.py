import pytest

from cvcutter.application.services.synchronization_service import choose_sync_path


def test_single_source_path() -> None:
    assert choose_sync_path(1, has_embedded_video_audio=True) == "auto_skip"


def test_single_external_source_requires_manual_sync() -> None:
    assert choose_sync_path(1, has_embedded_video_audio=False) == "manual_sync"


def test_invalid_audio_source_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        choose_sync_path(0)
