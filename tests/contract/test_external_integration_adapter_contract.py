from cvcutter.infrastructure.integrations.adapters import ApprovedAdapters


def test_adapter_publish_requires_fields() -> None:
    adapters = ApprovedAdapters()
    bad = adapters.publish_segment("s1", {"title": "a"})
    good = adapters.publish_segment("s1", {"title": "a", "destination": "youtube"})
    assert not bad.ok
    assert good.ok
