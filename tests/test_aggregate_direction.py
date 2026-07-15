from mf_screener.aggregate import _direction


def test_direction_increase() -> None:
    assert _direction(2, 0, 10.0, None) == "increase"


def test_direction_mixed() -> None:
    assert _direction(1, 1, 5.0, None) == "mixed"


def test_direction_decrease() -> None:
    assert _direction(0, 2, -5.0, None) == "decrease"
