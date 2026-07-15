"""End-to-end screener run: load → aggregate → filter → optional prices."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from mf_screener.aggregate import RankMode, StockAggregate, aggregate_by_stock
from mf_screener.load import load_holdings_from_folder
from mf_screener.metrics import enrich_all
from mf_screener.prices import entry_estimate_dict, fetch_prices
from mf_screener.report_month import resolve_report_month
from mf_screener.reporting.filters import filter_for_report
from mf_screener.reporting.symbol_context import NameMapContext
from mf_screener.symbol_map import NAME_TO_NSE_PATH, resolve_nse


@dataclass
class RunResult:
    stocks: list[StockAggregate]
    stocks_all: list[StockAggregate]
    price_month: str | None
    entry_by_key: dict[str, dict]


def resolve_price_month(folder: Path) -> str | None:
    try:
        return resolve_report_month(folder)
    except ValueError as exc:
        print(f"Warning: {exc}", file=sys.stderr)
        return None


def attach_entry_estimates(
    stocks: list[StockAggregate],
    folder: Path,
    *,
    refresh: bool,
    price_month: str | None,
    name_map: NameMapContext,
) -> tuple[str | None, dict[str, dict]]:
    if not NAME_TO_NSE_PATH.is_file():
        print(
            f"Warning: {NAME_TO_NSE_PATH} not found; skipping price enrichment.",
            file=sys.stderr,
        )
        return price_month, {}

    month = price_month
    if not month:
        try:
            month = resolve_report_month(folder)
        except ValueError as exc:
            print(f"Warning: {exc}; skipping price enrichment.", file=sys.stderr)
            return None, {}

    listings: list[tuple[str, str]] = []
    resolve_by_key: dict[str, str | None] = {}
    for stock in stocks:
        listed = resolve_nse(
            name=stock.name, nse_from_row=stock.nse, name_map=name_map.mapping
        )
        code = listed.code if listed else None
        resolve_by_key[stock.stock_key] = code
        if listed:
            listings.append((listed.code, listed.exchange))

    snapshots = fetch_prices(listings, month, refresh=refresh)
    entry_by_key: dict[str, dict] = {}
    for stock in stocks:
        nse = resolve_by_key.get(stock.stock_key)
        if not nse:
            entry_by_key[stock.stock_key] = entry_estimate_dict(None, unmapped=True)
        else:
            entry_by_key[stock.stock_key] = entry_estimate_dict(snapshots.get(nse))
    return month, entry_by_key


def run(
    folder: Path,
    *,
    rank_mode: RankMode = "composite",
    include_holds: bool = False,
    weight_scale: float = 10.0,
    new_boost: float = 50.0,
    enrich_prices: bool = False,
    refresh_prices: bool = False,
) -> RunResult:
    holdings = load_holdings_from_folder(folder)
    metrics = enrich_all(holdings)
    stocks_all = aggregate_by_stock(
        metrics,
        rank_mode=rank_mode,
        weight_scale=weight_scale,
        new_boost=new_boost,
    )
    stocks = filter_for_report(stocks_all, include_holds=include_holds)
    price_month = resolve_price_month(folder)
    entry_by_key: dict[str, dict] = {}
    if enrich_prices:
        name_map = NameMapContext.load()
        price_month, entry_by_key = attach_entry_estimates(
            stocks,
            folder,
            refresh=refresh_prices,
            price_month=price_month,
            name_map=name_map,
        )
    return RunResult(
        stocks=stocks,
        stocks_all=stocks_all,
        price_month=price_month,
        entry_by_key=entry_by_key,
    )
