from pathlib import Path

from mf_screener.aggregate import aggregate_by_stock
from mf_screener.load import load_holdings_from_folder
from mf_screener.metrics import enrich_all
from mf_screener.pipeline import run
from mf_screener.reporting.filters import filter_for_report
from mf_screener.reporting.payload import build_stock_payloads_from_aggregates


def test_mini_html_payload_merged_wockhardt(mini_june_folder: Path) -> None:
    result = run(mini_june_folder, enrich_prices=False)
    payloads = build_stock_payloads_from_aggregates(result.stocks, None)
    assert len(payloads) >= 1
    wock = [p for p in payloads if "Wockhardt" in p["stockName"]]
    assert len(wock) == 1
    assert wock[0]["fundCount"] == 2
    assert wock[0]["score"] > 0
    assert "mixedSignal" in wock[0]


def test_actionable_only_payload_count(mini_june_folder: Path) -> None:
    holdings = load_holdings_from_folder(mini_june_folder)
    all_stocks = aggregate_by_stock(enrich_all(holdings))
    active = filter_for_report(all_stocks, include_holds=False)
    payloads = build_stock_payloads_from_aggregates(active, None)
    assert len(payloads) == len(active)
    for p in payloads:
        assert p["addCount"] > 0 or p["reduceCount"] > 0
