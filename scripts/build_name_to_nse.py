#!/usr/bin/env python3
"""Build config/name_to_nse.csv from NSE EQUITY_L and fund holding names."""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mf_screener.load import canonical_holding_display_name, load_holdings_from_folder
from mf_screener.symbol_map import ListedSymbol, normalize_company_name, normalize_company_name_compact

NSE_EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
DEFAULT_FUNDS = ROOT / "funds"
OUT_PATH = ROOT / "config" / "name_to_nse.csv"
MANUAL_PATH = ROOT / "config" / "nse_manual_overrides.csv"


def fetch_nse_equity_master() -> list[tuple[str, str]]:
    req = urllib.request.Request(
        NSE_EQUITY_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", errors="replace")
    rows: list[tuple[str, str]] = []
    for row in csv.DictReader(io.StringIO(raw)):
        sym = (row.get("SYMBOL") or "").strip().upper()
        name = (row.get("NAME OF COMPANY") or "").strip()
        if sym and name:
            rows.append((sym, name))
    return rows


def load_manual_overrides(path: Path) -> dict[str, ListedSymbol]:
    if not path.is_file():
        return {}
    out: dict[str, ListedSymbol] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not row:
                continue
            name = (row.get("company_name") or "").strip()
            code = (row.get("nse") or "").strip().upper()
            if name.startswith("#") or not name or not code:
                continue
            exchange = (row.get("exchange") or "NSE").strip().upper()
            if exchange in ("NS", "NSE"):
                exchange = "NSE"
            elif exchange in ("BO", "BSE"):
                exchange = "BSE"
            listed = ListedSymbol(code=code, exchange=exchange)
            out[normalize_company_name(name)] = listed
            out.setdefault(normalize_company_name_compact(name), listed)
    return out


def is_equity_holding_name(name: str) -> bool:
    text = (name or "").strip()
    if not text or text.startswith("("):
        return False
    if text.startswith("^^"):
        text = text[2:].strip()
    if not text:
        return False
    low = text.lower()
    skip_markers = (
        "tbill",
        "treasury bill",
        "g-sec",
        "government security",
        "certificate of deposit",
        "commercial paper",
        "repo instruments",
        "treps",
        "cash & cash",
        "net current asset",
        "mutual funds units",
        "reits",
        "invits",
        "total outstanding exposure",
        "clearing corporation",
    )
    return not any(m in low for m in skip_markers)


def collect_fund_company_names(funds_root: Path) -> list[str]:
    names: set[str] = set()
    for folder in sorted(funds_root.iterdir()):
        if not folder.is_dir():
            continue
        for row in load_holdings_from_folder(folder):
            if is_equity_holding_name(row.name):
                names.add(row.name.strip())
    return sorted(names)


def build_nse_lookup(
    nse_rows: list[tuple[str, str]],
) -> tuple[dict[str, str], dict[str, str], dict[str, list[str]]]:
    by_norm: dict[str, str] = {}
    by_compact: dict[str, str] = {}
    conflicts: dict[str, list[str]] = {}
    for sym, name in nse_rows:
        key = normalize_company_name(name)
        compact = normalize_company_name_compact(name)
        if key in by_norm and by_norm[key] != sym:
            conflicts.setdefault(key, sorted({by_norm[key], sym}))
        else:
            by_norm[key] = sym
        if compact not in by_compact:
            by_compact[compact] = sym
    return by_norm, by_compact, conflicts


def resolve_symbol(
    company_name: str,
    *,
    nse_by_norm: dict[str, str],
    nse_by_compact: dict[str, str],
    manual: dict[str, ListedSymbol],
) -> ListedSymbol | None:
    key = normalize_company_name(company_name)
    if key in manual:
        return manual[key]
    if key in nse_by_norm:
        return ListedSymbol(code=nse_by_norm[key], exchange="NSE")
    compact = normalize_company_name_compact(company_name)
    if compact in manual:
        return manual[compact]
    code = nse_by_compact.get(compact)
    if code:
        return ListedSymbol(code=code, exchange="NSE")
    return None


def dedupe_mapped_by_norm(
    mapped: list[tuple[str, ListedSymbol]],
) -> list[tuple[str, ListedSymbol]]:
    """One output row per normalized company name; canonical display spelling."""
    by_norm: dict[str, list[tuple[str, ListedSymbol]]] = {}
    for name, listed in mapped:
        by_norm.setdefault(normalize_company_name(name), []).append((name, listed))

    deduped: list[tuple[str, ListedSymbol]] = []
    for _key, group in by_norm.items():
        names = [n for n, _ in group]
        display = canonical_holding_display_name(names)
        listed = next((l for n, l in group if n == display), group[0][1])
        deduped.append((display, listed))
    deduped.sort(key=lambda item: item[0].lower())
    return deduped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--funds",
        type=Path,
        default=DEFAULT_FUNDS,
        help="Root folder containing month subfolders of fund CSVs",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT_PATH,
        help="Output CSV path",
    )
    parser.add_argument(
        "--report-unmapped",
        action="store_true",
        help="Print fund equity names that could not be matched on NSE",
    )
    args = parser.parse_args()

    nse_rows = fetch_nse_equity_master()
    nse_by_norm, nse_by_compact, conflicts = build_nse_lookup(nse_rows)
    manual = load_manual_overrides(MANUAL_PATH)

    fund_names = collect_fund_company_names(args.funds)
    mapped: list[tuple[str, ListedSymbol]] = []
    unmapped: list[str] = []
    for name in fund_names:
        listed = resolve_symbol(
            name,
            nse_by_norm=nse_by_norm,
            nse_by_compact=nse_by_compact,
            manual=manual,
        )
        if listed:
            mapped.append((name, listed))
        else:
            unmapped.append(name)

    # Ensure manual-only rows (e.g. SME/BSE) are present with exact CSV spelling.
    mapped_keys = {normalize_company_name(n) for n, _ in mapped}
    with MANUAL_PATH.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("company_name") or "").strip()
            code = (row.get("nse") or "").strip().upper()
            if not name or not code or name.startswith("#"):
                continue
            if normalize_company_name(name) in mapped_keys:
                continue
            exchange = (row.get("exchange") or "NSE").strip().upper()
            if exchange in ("NS", "NSE"):
                exchange = "NSE"
            elif exchange in ("BO", "BSE"):
                exchange = "BSE"
            listed = ListedSymbol(code=code, exchange=exchange)
            mapped.append((name, listed))
            mapped_keys.add(normalize_company_name(name))

    mapped.sort(key=lambda item: item[0].lower())
    mapped = dedupe_mapped_by_norm(mapped)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["company_name", "nse", "exchange"])
        for name, listed in mapped:
            writer.writerow([name, listed.code, listed.exchange])

    print(f"NSE listings: {len(nse_rows)}")
    print(f"Normalized NSE keys: {len(nse_by_norm)} (conflicts: {len(conflicts)})")
    print(f"Fund equity names: {len(fund_names)}")
    print(f"Mapped -> {args.out}: {len(mapped)}")
    print(f"Unmapped: {len(unmapped)}")
    if args.report_unmapped and unmapped:
        print("\nUnmapped fund names:")
        for name in unmapped:
            print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
