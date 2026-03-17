from cvcutter.infrastructure.media.export_pipeline import render_opening_title, validate_export_format


def test_format_and_title_overlay() -> None:
    assert validate_export_format("mp4")
    assert render_opening_title(True, 3)["enabled"]
