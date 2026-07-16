"""Tests for RupeeVest ingest (no network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mf_screener.ingest.rupeevest import (
    FundSearchIndex,
    default_output_slug,
    download_fund_csv,
    fund_slug_prefix,
    index_from_search_payload,
    portfolio_tracker_to_csv_text,
    _format_aum_cr,
    _http_get_json,
    _token_in_name,
)
from mf_screener.load import load_fund_csv

SAMPLE_PAYLOAD = {
    "month_name": ["Jun-26", "May-26"],
    "MonthwiseAUM": [{"aum": "100.0"}, {"aum": "90.0"}],
    "stock_data": [
        [{"fincode": 1, "percent_aum": "2.5", "noshares": 1000}],
        [{"fincode": 1, "percent_aum": "2.0", "noshares": 900}],
    ],
    "stock_mapping": {"1": "Example Company Limited"},
}


def test_default_output_slug() -> None:
    assert fund_slug_prefix("Abakkus Small Cap Fund-Reg(G)") == "abakkus_small_cap"
    assert (
        default_output_slug("Abakkus Small Cap Fund-Reg(G)", "Jun-26")
        == "abakkus_small_cap_06_26"
    )


def test_portfolio_tracker_csv_loads(tmp_path: Path) -> None:
    text = portfolio_tracker_to_csv_text(SAMPLE_PAYLOAD)
    path = tmp_path / "sample_06_26.csv"
    path.write_text(text, encoding="utf-8")
    rows = load_fund_csv(path)
    assert len(rows) == 1
    assert rows[0].name == "Example Company Limited"
    assert rows[0].current_weight_pct == 2.5
    assert rows[0].prior_weight_pct == 2.0


def test_format_aum_cr() -> None:
    assert _format_aum_cr(None) == "-"
    assert _format_aum_cr("-") == "-"
    assert _format_aum_cr("100.0") == "100.0"
    assert _format_aum_cr("1,234.56") == "1234.6"
    assert _format_aum_cr("not-a-number") == "not-a-number"


def test_token_in_name_avoids_substring_false_positive() -> None:
    assert _token_in_name("abakkus small cap fund", "cap")
    assert not _token_in_name("hdfc capital builder", "cap")
    assert _token_in_name("hdfc capital builder", "capital")


def test_resolve_exact_case_insensitive_and_fuzzy() -> None:
    index = FundSearchIndex.from_mapping(
        {
            "Abakkus Small Cap Fund-Reg(G)": "111",
            "HDFC Capital Builder Fund-Reg(G)": "222",
        }
    )
    assert index.resolve("Abakkus Small Cap Fund-Reg(G)") == (
        "Abakkus Small Cap Fund-Reg(G)",
        "111",
    )
    assert index.resolve("abakkus small cap fund-reg(g)") == (
        "Abakkus Small Cap Fund-Reg(G)",
        "111",
    )
    hit = index.resolve("abakkus small cap")
    assert hit is not None
    assert hit[1] == "111"
    capital_only = FundSearchIndex.from_mapping(
        {"HDFC Capital Builder Fund-Reg(G)": "222"}
    )
    assert capital_only.resolve("cap") is None
    assert capital_only.resolve("capital builder")[1] == "222"


def test_index_from_search_payload_collisions() -> None:
    index = index_from_search_payload(
        {
            "search_data": [{"s_name1": "Same Fund", "schemecode": "1"}],
            "search_data_nfo": [{"s_name1": "Same Fund", "schemecode": "2"}],
        }
    )
    assert index.by_exact_name["Same Fund"] == "1"
    assert len(index.collisions) == 1
    assert "ignored 2" in index.collisions[0]


def test_download_fund_csv_no_match(tmp_path: Path) -> None:
    index = FundSearchIndex.from_mapping({"Known Fund": "9"})
    result = download_fund_csv(
        fund_query="Missing Fund",
        out_dir=tmp_path,
        index=index,
    )
    assert result.error
    assert result.path is None


def test_download_skips_existing_csv_without_tracker_fetch(tmp_path: Path) -> None:
    index = FundSearchIndex.from_mapping({"Demo Fund-Reg(G)": "42"})
    existing = tmp_path / "demo_06_26.csv"
    existing.write_text("already here", encoding="utf-8")
    with patch(
        "mf_screener.ingest.rupeevest.fetch_portfolio_tracker",
    ) as fetch:
        result = download_fund_csv(
            fund_query="Demo Fund-Reg(G)",
            out_dir=tmp_path,
            index=index,
            overwrite=False,
        )
    fetch.assert_not_called()
    assert result.error and "exists" in result.error
    assert result.path == existing


def test_download_fund_csv_writes(tmp_path: Path) -> None:
    index = FundSearchIndex.from_mapping({"Demo Fund-Reg(G)": "42"})
    with patch(
        "mf_screener.ingest.rupeevest.fetch_portfolio_tracker",
        return_value=SAMPLE_PAYLOAD,
    ):
        result = download_fund_csv(
            fund_query="Demo Fund-Reg(G)",
            out_dir=tmp_path,
            index=index,
        )
    assert result.error is None
    assert result.path is not None
    assert "Equity Holdings" in result.path.read_text(encoding="utf-8")


def test_download_overwrite(tmp_path: Path) -> None:
    index = FundSearchIndex.from_mapping({"Demo Fund-Reg(G)": "42"})
    with patch(
        "mf_screener.ingest.rupeevest.fetch_portfolio_tracker",
        return_value=SAMPLE_PAYLOAD,
    ):
        first = download_fund_csv(
            fund_query="Demo",
            out_dir=tmp_path,
            index=index,
        )
        assert first.path is not None
        first.path.write_text("stale", encoding="utf-8")
        again = download_fund_csv(
            fund_query="Demo",
            out_dir=tmp_path,
            index=index,
            overwrite=True,
        )
    assert again.error is None
    assert again.path is not None
    assert "Equity Holdings" in again.path.read_text(encoding="utf-8")


def test_http_get_json_retries_on_url_error() -> None:
    import urllib.error

    boom = urllib.error.URLError("temporary")
    ok_resp = MagicMock()
    ok_resp.read.return_value = b'{"ok": true}'
    ok_resp.__enter__.return_value = ok_resp
    ok_resp.__exit__.return_value = False

    with (
        patch("mf_screener.ingest.rupeevest.urllib.request.urlopen") as urlopen,
        patch("mf_screener.ingest.rupeevest.time.sleep") as sleep,
    ):
        urlopen.side_effect = [boom, ok_resp]
        data = _http_get_json("/home/get_search_data")
    assert data == {"ok": True}
    assert urlopen.call_count == 2
    sleep.assert_called_once()


def test_http_get_json_raises_after_retries() -> None:
    import urllib.error

    boom = urllib.error.URLError("down")
    with (
        patch("mf_screener.ingest.rupeevest.urllib.request.urlopen", side_effect=boom),
        patch("mf_screener.ingest.rupeevest.time.sleep"),
        pytest.raises(urllib.error.URLError),
    ):
        _http_get_json("/home/get_search_data")
