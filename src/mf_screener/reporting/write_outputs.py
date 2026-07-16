"""Shared JSON / CSV / HTML / combined report writers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mf_screener.aggregate import StockAggregate
from mf_screener.pipeline import RunResult
from mf_screener.report_csv import write_csv_report
from mf_screener.report_html import HtmlReportMeta, refresh_combined_html_report, write_html_report
from mf_screener.reporting.json_report import build_report
from mf_screener.reporting.symbol_context import NameMapContext


def write_traction_reports(
    result: RunResult,
    *,
    folder: Path,
    out_json: Path,
    rank: str,
    include_holds: bool,
    name_map: NameMapContext | None = None,
    csv_path: Path | None = None,
    html_path: Path | None = None,
    combined_html: Path | None = None,
    refresh_combined: bool = True,
) -> dict[str, Path]:
    """Write sibling JSON/CSV/HTML and optionally refresh multi-month traction.html."""
    name_map = name_map or NameMapContext.load()
    stocks: list[StockAggregate] = result.stocks
    entry_by_key = result.entry_by_key or None

    out_json.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(
        stocks,
        folder=folder,
        rank=rank,
        stock_count_total=len(result.stocks_all),
        include_holds=include_holds,
        price_month=result.price_month,
        entry_by_stock_key=entry_by_key,
    )
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote JSON report to {out_json}", file=sys.stderr)

    csv_out = csv_path or out_json.with_suffix(".csv")
    write_csv_report(stocks, csv_out, entry_by_stock_key=entry_by_key, name_map=name_map)
    print(f"Wrote CSV report to {csv_out}", file=sys.stderr)

    html_out = html_path or out_json.with_suffix(".html")
    write_html_report(
        stocks,
        html_out,
        meta=HtmlReportMeta(
            folder=str(folder.resolve()),
            price_month=result.price_month,
            rank_mode=rank,
            include_holds=include_holds,
        ),
        entry_by_stock_key=entry_by_key,
        name_map=name_map,
    )
    print(f"Wrote HTML report to {html_out}", file=sys.stderr)

    paths: dict[str, Path] = {
        "json": out_json,
        "csv": csv_out,
        "html": html_out,
    }

    if refresh_combined:
        combined = combined_html or (out_json.parent / "traction.html")
        if refresh_combined_html_report(
            out_json.parent,
            combined,
            prefer_month_id=result.price_month,
            name_map=name_map,
        ):
            print(f"Wrote combined HTML report to {combined}", file=sys.stderr)
            paths["combined"] = combined

    return paths
