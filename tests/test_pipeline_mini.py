from pathlib import Path

from mf_screener.aggregate import aggregate_by_stock
from mf_screener.reporting.filters import filter_for_report
from mf_screener.load import load_holdings_from_folder
from mf_screener.metrics import enrich_all
from mf_screener.symbol_map import normalize_company_name


def test_mini_fixture_merges_wockhardt(mini_june_folder: Path) -> None:
    holdings = load_holdings_from_folder(mini_june_folder)
    metrics = enrich_all(holdings)
    all_stocks = aggregate_by_stock(metrics)
    stocks = filter_for_report(all_stocks, include_holds=False)
    names = {s.name for s in stocks}
    assert any("Wockhardt" in n for n in names)
    wock = [s for s in stocks if "Wockhardt" in s.name]
    assert len(wock) == 1
    assert wock[0].fund_count == 2


def test_mini_fixture_excludes_hold_only_corp(mini_june_folder: Path) -> None:
    holdings = load_holdings_from_folder(mini_june_folder)
    metrics = enrich_all(holdings)
    all_stocks = aggregate_by_stock(metrics)
    stocks = filter_for_report(all_stocks, include_holds=False)
    norms = {normalize_company_name(s.name) for s in stocks}
    assert normalize_company_name("Hold Only Corp Limited") not in norms
