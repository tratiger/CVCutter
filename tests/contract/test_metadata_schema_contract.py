from cvcutter.application.services.metadata_import_service import normalize_metadata, validate_metadata_version


def test_metadata_alias_and_version_contract() -> None:
    normalized = normalize_metadata({"performer_name": "A", "song_title": "B"})
    assert normalized["performer"] == "A"
    assert not validate_metadata_version("v2").ok
