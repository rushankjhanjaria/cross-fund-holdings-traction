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
from mf_screener.reporting.layout import ReportsLayout
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
    """Write JSON/CSV/HTML into the structured reports layout and optionally refresh combined HTML."""
    name_map = name_map or NameMapContext.load()
    stocks: list[StockAggregate] = result.stocks
    entry_by_key = result.entry_by_key or None

    layout = ReportsLayout.from_any_path(out_json)
    layout.ensure()
    slug = ReportsLayout.slug_from_traction_json(out_json)
    paths = layout.for_slug(slug)

    json_out = paths.traction_json
    csv_out = csv_path or paths.traction_csv
    html_out = html_path or paths.traction_html
    combined = combined_html or paths.combined_html

    json_out.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(
        stocks,
        folder=folder,
        rank=rank,
        stock_count_total=len(result.stocks_all),
        include_holds=include_holds,
        price_month=result.price_month,
        entry_by_stock_key=entry_by_key,
    )
    json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote JSON report to {json_out}", file=sys.stderr)

    write_csv_report(stocks, csv_out, entry_by_stock_key=entry_by_key, name_map=name_map)
    print(f"Wrote CSV report to {csv_out}", file=sys.stderr)

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

    written: dict[str, Path] = {
        "json": json_out,
        "csv": csv_out,
        "html": html_out,
        "root": layout.root,
    }

    if refresh_combined:
        if refresh_combined_html_report(
            layout.root,
            combined,
            prefer_month_id=result.price_month,
            name_map=name_map,
        ):
            print(f"Wrote combined HTML report to {combined}", file=sys.stderr)
            written["combined"] = combined

    return written
