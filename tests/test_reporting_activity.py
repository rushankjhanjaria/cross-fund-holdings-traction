from mf_screener.reporting.activity import is_mixed_signal


def test_mixed_requires_two_kinds() -> None:
    assert not is_mixed_signal(1, 0, 0)
    assert is_mixed_signal(1, 0, 1)
    assert is_mixed_signal(0, 1, 1)
    assert is_mixed_signal(1, 1, 0)
