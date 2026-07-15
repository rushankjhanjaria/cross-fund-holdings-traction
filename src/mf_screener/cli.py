"""CLI: run traction screener on a folder of fund CSVs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mf_screener.aggregate import RankMode
from mf_screener.pipeline import run
from mf_screener.report_csv import write_csv_report
from mf_screener.report_html import HtmlReportMeta, refresh_combined_html_report, write_html_report
from mf_screener.reporting.json_report import build_report
from mf_screener.reporting.symbol_context import NameMapContext
from mf_screener.reporting.terminal import print_tree


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Screen mutual fund holdings for cross-fund stock traction.",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        required=True,
        help="Directory containing one CSV per fund (e.g. funds/june)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON report to this path",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Write CSV report (default: same path as --out with .csv extension)",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Write HTML report (default: same path as --out with .html extension)",
    )
    parser.add_argument(
        "--combined-html",
        type=Path,
        default=None,
        help="Multi-month HTML from all output/*_traction.json (default: output/traction.html)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        help="Max stocks to print in terminal tree (default: 50)",
    )
    parser.add_argument(
        "--rank",
        choices=("composite", "share_activity", "mean_weight_delta", "new_entries"),
        default="composite",
        help="Ranking mode (default: composite)",
    )
    parser.add_argument(
        "--weight-scale",
        type=float,
        default=10.0,
        help="Scale median weight delta in composite score (default: 10)",
    )
    parser.add_argument(
        "--new-boost",
        type=float,
        default=50.0,
        help="Score boost per new fund entry in composite (default: 50)",
    )
    parser.add_argument(
        "--include-holds",
        action="store_true",
        help="Also include aggregate hold-only stocks with no buy/sell (default: exclude)",
    )
    parser.add_argument(
        "--enrich-prices",
        action="store_true",
        help="Attach MF entry band estimates via yfinance (config/name_to_nse.csv)",
    )
    parser.add_argument(
        "--refresh-prices",
        action="store_true",
        help="Ignore cached yfinance data for this run",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(
            args.folder,
            rank_mode=args.rank,  # type: ignore[arg-type]
            include_holds=args.include_holds,
            weight_scale=args.weight_scale,
            new_boost=args.new_boost,
            enrich_prices=args.enrich_prices,
            refresh_prices=args.refresh_prices,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    stocks = result.stocks
    name_map = NameMapContext.load()
    entry_by_key = result.entry_by_key or None

    print_tree(stocks, top=args.top)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        report = build_report(
            stocks,
            folder=args.folder,
            rank=args.rank,
            stock_count_total=len(result.stocks_all),
            include_holds=args.include_holds,
            price_month=result.price_month,
            entry_by_stock_key=entry_by_key,
        )
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote JSON report to {args.out}", file=sys.stderr)

        csv_path = args.csv if args.csv is not None else args.out.with_suffix(".csv")
        write_csv_report(stocks, csv_path, entry_by_stock_key=entry_by_key, name_map=name_map)
        print(f"Wrote CSV report to {csv_path}", file=sys.stderr)

        html_path = args.html if args.html is not None else args.out.with_suffix(".html")
        write_html_report(
            stocks,
            html_path,
            meta=HtmlReportMeta(
                folder=str(args.folder.resolve()),
                price_month=result.price_month,
                rank_mode=args.rank,
                include_holds=args.include_holds,
            ),
            entry_by_stock_key=entry_by_key,
            name_map=name_map,
        )
        print(f"Wrote HTML report to {html_path}", file=sys.stderr)

        combined_path = args.combined_html or (args.out.parent / "traction.html")
        if refresh_combined_html_report(
            args.out.parent,
            combined_path,
            prefer_month_id=result.price_month,
            name_map=name_map,
        ):
            print(f"Wrote combined HTML report to {combined_path}", file=sys.stderr)
    elif args.csv:
        write_csv_report(stocks, args.csv, entry_by_stock_key=entry_by_key, name_map=name_map)
        print(f"Wrote CSV report to {args.csv}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
