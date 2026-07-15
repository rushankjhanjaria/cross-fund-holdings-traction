"""Flat CSV report for traction screener results."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, TextIO

from mf_screener.aggregate import StockAggregate
from mf_screener.reporting.activity import fund_csv_activity
from mf_screener.reporting.format import (
    entry_csv_fields_for_stock,
    format_pct_of_aum,
    format_share_pct_change,
    stock_csv_direction,
)
from mf_screener.reporting.symbol_context import NameMapContext


def resolve_stock_ticker(
    stock: StockAggregate,
    entry_by_stock_key: dict[str, dict] | None = None,
    name_map: NameMapContext | None = None,
) -> str:
    """NSE/BSE code for reports (holdings row, price enrichment, or name map)."""
    est = (entry_by_stock_key or {}).get(stock.stock_key)
    ctx = name_map or NameMapContext.load()
    return ctx.resolve_ticker(
        name=stock.name,
        nse_from_row=stock.nse or stock.bse,
        entry_estimate=est if isinstance(est, dict) else None,
    )


def iter_csv_rows(
    stocks: Iterable[StockAggregate],
    entry_by_stock_key: dict[str, dict] | None = None,
    name_map: NameMapContext | None = None,
) -> Iterable[dict[str, str]]:
    ctx = name_map or NameMapContext.load()
    for stock in stocks:
        direction = stock_csv_direction(stock)
        nse = resolve_stock_ticker(stock, entry_by_stock_key, ctx)
        price_fields = entry_csv_fields_for_stock(stock, entry_by_stock_key)
        emitted = False
        for fund in stock.funds:
            activity = fund_csv_activity(fund)
            if activity is None:
                continue
            emitted = True
            yield {
                "stock_name": stock.name,
                "nse": nse,
                "stock_direction": direction,
                "fund_name": fund.fund_display_name,
                "activity": activity,
                "share_pct_change": format_share_pct_change(fund),
                "pct_of_aum": format_pct_of_aum(fund),
                **price_fields,
            }
        if not emitted and stock.fund_count > 0:
            yield {
                "stock_name": stock.name,
                "nse": nse,
                "stock_direction": direction,
                "fund_name": "",
                "activity": "",
                "share_pct_change": "",
                "pct_of_aum": "",
                **price_fields,
            }


CSV_FIELDNAMES = [
    "stock_name",
    "nse",
    "stock_direction",
    "fund_name",
    "activity",
    "share_pct_change",
    "pct_of_aum",
    "month_high",
    "month_low",
    "estimated_entry_mid",
    "close_latest",
    "pct_vs_entry_mid",
]


def write_csv_report(
    stocks: list[StockAggregate],
    path: Path,
    entry_by_stock_key: dict[str, dict] | None = None,
    name_map: NameMapContext | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        write_csv_report_to_stream(
            stocks, f, entry_by_stock_key=entry_by_stock_key, name_map=name_map
        )


def write_csv_report_to_stream(
    stocks: list[StockAggregate],
    stream: TextIO,
    entry_by_stock_key: dict[str, dict] | None = None,
    name_map: NameMapContext | None = None,
) -> None:
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    for row in iter_csv_rows(stocks, entry_by_stock_key, name_map=name_map):
        writer.writerow(row)
