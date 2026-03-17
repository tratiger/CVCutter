from cvcutter.domain.segmentation.boundary_aggregator import aggregate_boundaries


def test_multimodal_boundary_aggregation() -> None:
    value = aggregate_boundaries([(10.0, 0.2), (20.0, 0.8)])
    assert 17 <= value <= 19
