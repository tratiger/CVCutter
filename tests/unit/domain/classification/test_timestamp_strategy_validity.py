from cvcutter.domain.classification.timestamp_validator import validate_timestamp_strategy


def test_timestamp_strategy_validity() -> None:
    assert validate_timestamp_strategy(False, "embedded") == (False, "embedded timestamp missing")
