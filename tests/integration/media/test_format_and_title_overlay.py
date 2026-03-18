from cvcutter.infrastructure.media.export_pipeline import (
    render_opening_title,
    validate_export_format,
    validate_input_media_format,
)


def test_format_and_title_overlay() -> None:
    assert validate_input_media_format("mkv")
    assert validate_input_media_format("mts")
    assert validate_input_media_format("wav")
    assert validate_export_format("mp4")
    assert not validate_export_format("mkv")
    assert not validate_export_format("mts")
    assert not validate_export_format("avi")
    assert render_opening_title(True, 3)["enabled"]
