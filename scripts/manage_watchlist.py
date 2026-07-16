#!/usr/bin/env python3
"""Manage reports/watchlist.json beside traction reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mf_screener.reporting.watchlist import (  # noqa: E402
    add_manual_item,
    load_watchlist,
    remove_item,
    save_watchlist,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reports-dir",
        type=Path,
        required=True,
        help="Directory containing *_traction.json and watchlist.json",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List watchlist items")

    add_p = sub.add_parser("add", help="Pin a stock manually")
    add_p.add_argument("--key", required=True, help="stockKey e.g. NSE:MEESHO or NAME:…")
    add_p.add_argument("--name", default="", help="Display name")
    add_p.add_argument("--nse", default="", help="NSE symbol")
    add_p.add_argument("--pinned-at", default="", help="Month id e.g. 2026-06")

    rm_p = sub.add_parser("remove", help="Remove a stock by stockKey")
    rm_p.add_argument("--key", required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    reports_dir = args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    wl = load_watchlist(reports_dir)

    if args.command == "list":
        items = wl.get("items") or []
        if not items:
            print("(empty)")
            return 0
        for item in items:
            print(
                f"{item.get('stockKey')}\t{item.get('name')}\t"
                f"{item.get('nse')}\t{item.get('source')}\t{item.get('pinnedAt')}"
            )
        return 0

    if args.command == "add":
        wl = add_manual_item(
            wl,
            stock_key=args.key,
            name=args.name,
            nse=args.nse,
            pinned_at=args.pinned_at,
        )
        path = save_watchlist(reports_dir, wl)
        print(f"Wrote {path}", file=sys.stderr)
        return 0

    if args.command == "remove":
        wl = remove_item(wl, args.key)
        path = save_watchlist(reports_dir, wl)
        print(f"Wrote {path}", file=sys.stderr)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
