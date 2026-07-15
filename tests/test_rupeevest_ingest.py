"""Tests for RupeeVest ingest (no network)."""

from mf_screener.ingest.rupeevest import (
    default_output_slug,
    portfolio_tracker_to_csv_text,
)
from mf_screener.load import load_fund_csv
from pathlib import Path


def test_default_output_slug() -> None:
    assert (
        default_output_slug("Abakkus Small Cap Fund-Reg(G)", "Jun-26")
        == "abakkus_small_cap_06_26"
    )


def test_portfolio_tracker_csv_loads(tmp_path: Path) -> None:
    payload = {
        "month_name": ["Jun-26", "May-26"],
        "MonthwiseAUM": [{"aum": "100.0"}, {"aum": "90.0"}],
        "stock_data": [
            [{"fincode": 1, "percent_aum": "2.5", "noshares": 1000}],
            [{"fincode": 1, "percent_aum": "2.0", "noshares": 900}],
        ],
        "stock_mapping": {"1": "Example Company Limited"},
    }
    text = portfolio_tracker_to_csv_text(payload)
    path = tmp_path / "sample_06_26.csv"
    path.write_text(text, encoding="utf-8")
    rows = load_fund_csv(path)
    assert len(rows) == 1
    assert rows[0].name == "Example Company Limited"
    assert rows[0].current_weight_pct == 2.5
    assert rows[0].prior_weight_pct == 2.0
