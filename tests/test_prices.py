"""Price snapshot helpers (no network)."""

from __future__ import annotations

import pandas as pd

from mf_screener.prices import _sma_asof_month_end, _snapshot_from_history


def test_sma_asof_month_end_full_window() -> None:
    idx = pd.date_range("2026-03-01", periods=40, freq="B")
    closes = pd.Series(range(40), index=idx, dtype=float)
    sma = _sma_asof_month_end(closes)
    assert sma == float(closes.iloc[-30:].mean())


def test_snapshot_pct_vs_sma() -> None:
    idx = pd.date_range("2026-03-01", periods=50, freq="B")
    closes = pd.Series([100.0 + i for i in range(50)], index=idx)
    df = pd.DataFrame(
        {
            "High": closes + 1,
            "Low": closes - 1,
            "Close": closes,
        }
    )
    snap = _snapshot_from_history("TEST", "2026-04", df)
    assert snap.status == "ok"
    assert snap.sma_30 is not None
    assert snap.month_end_close is not None
    assert snap.pct_vs_sma is not None
    assert snap.close_latest == float(closes.iloc[-1])
