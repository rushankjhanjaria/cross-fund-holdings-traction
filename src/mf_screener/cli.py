"""CLI: run traction screener on a folder of fund CSVs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mf_screener.aggregate import (
    DEFAULT_BREADTH_BONUS,
    DEFAULT_EXIT_PENALTY,
    DEFAULT_HOLD_BONUS,
    DEFAULT_NEW_BOOST,
    DEFAULT_SHARE_WEIGHT,
    DEFAULT_WEIGHT_SCALE,
)
from mf_screener.pipeline import run
from mf_screener.report_csv import write_csv_report
from mf_screener.reporting.symbol_context import NameMapContext
from mf_screener.reporting.terminal import print_tree
from mf_screener.reporting.write_outputs import write_traction_reports


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
        help="Write JSON report path or filename under reports root (also writes csv/ + html/)",
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
        help="Multi-month HTML from reports html/traction.html (default under reports root)",
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
        default=DEFAULT_WEIGHT_SCALE,
        help=f"Scale median weight delta in composite score (default: {DEFAULT_WEIGHT_SCALE:g})",
    )
    parser.add_argument(
        "--new-boost",
        type=float,
        default=DEFAULT_NEW_BOOST,
        help=f"Score boost per new fund entry in composite (default: {DEFAULT_NEW_BOOST:g})",
    )
    parser.add_argument(
        "--breadth-bonus",
        type=float,
        default=DEFAULT_BREADTH_BONUS,
        help=f"Points per active (buying) fund in composite (default: {DEFAULT_BREADTH_BONUS:g})",
    )
    parser.add_argument(
        "--share-weight",
        type=float,
        default=DEFAULT_SHARE_WEIGHT,
        help=(
            "Weight on log1p(median share %% change) × breadth in composite "
            f"(default: {DEFAULT_SHARE_WEIGHT:g})"
        ),
    )
    parser.add_argument(
        "--exit-penalty",
        type=float,
        default=DEFAULT_EXIT_PENALTY,
        help=f"Penalty per fund reducing/exiting in composite (default: {DEFAULT_EXIT_PENALTY:g})",
    )
    parser.add_argument(
        "--hold-bonus",
        type=float,
        default=DEFAULT_HOLD_BONUS,
        help=(
            "Points per fund still holding (unchanged shares) in composite "
            f"(default: {DEFAULT_HOLD_BONUS:g}; kept below active breadth bonus)"
        ),
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
            breadth_bonus=args.breadth_bonus,
            share_weight=args.share_weight,
            exit_penalty=args.exit_penalty,
            hold_bonus=args.hold_bonus,
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
        write_traction_reports(
            result,
            folder=args.folder,
            out_json=args.out,
            rank=args.rank,
            include_holds=args.include_holds,
            name_map=name_map,
            csv_path=args.csv,
            html_path=args.html,
            combined_html=args.combined_html,
            refresh_combined=True,
        )
    elif args.csv:
        write_csv_report(stocks, args.csv, entry_by_stock_key=entry_by_key, name_map=name_map)
        print(f"Wrote CSV report to {args.csv}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
