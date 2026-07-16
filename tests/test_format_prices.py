"""Price field snake/camel contract."""

from __future__ import annotations

from mf_screener.reporting.format import (
    entry_price_fields_camel,
    entry_price_fields_camel_from_csv_row,
    primary_pct_vs,
)


def test_camel_prefers_sma_for_pct_vs_mid_alias() -> None:
    est = {
        "status": "ok",
        "month_high": 120.0,
        "month_low": 80.0,
        "estimated_entry_mid": 100.0,
        "month_end_close": 105.0,
        "sma_30": 95.0,
        "close_latest": 110.0,
        "pct_vs_entry_mid": 10.0,
        "pct_vs_sma": 15.789,
    }
    camel = entry_price_fields_camel(est)
    assert camel["sma30"]
    assert camel["pctVsSma"].startswith("15.789")
    assert camel["pctVsMid"] == camel["pctVsSma"]


def test_csv_row_mapping_matches_est_path() -> None:
    row = {
        "month_high": "120",
        "month_low": "80",
        "estimated_entry_mid": "100",
        "month_end_close": "105",
        "sma_30": "95",
        "close_latest": "110",
        "pct_vs_entry_mid": "10",
        "pct_vs_sma": "15.5",
    }
    camel = entry_price_fields_camel_from_csv_row(row)
    assert camel["pctVsSma"] == "15.5"
    assert camel["pctVsMid"] == "15.5"
    assert primary_pct_vs(row) == "15.5"
