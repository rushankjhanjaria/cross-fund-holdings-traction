"""Load Trendlyne mutual fund holding CSVs from a folder."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class HoldingRow:
    """One stock line in one fund's holdings export."""

    fund_slug: str
    fund_display_name: str
    name: str
    nse: str
    bse: str
    sector: str
    current_value: float
    prior_value: float
    current_weight_pct: float
    quantity: float | None
    share_change_abs: float | None
    share_change_raw: str
    history_url: str
    prior_weight_pct: float | None = None


def discover_csv_paths(folder: Path) -> list[Path]:
    folder = folder.resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")
    paths = sorted(folder.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No CSV files in {folder}")
    return paths


def slug_from_filename(path: Path) -> str:
    return path.stem


def display_name_from_slug(slug: str) -> str:
    """helios_small_cap_direct_growth_06 -> Helios Small Cap Direct Growth."""
    parts = slug.split("_")
    trimmed = parts
    if parts and parts[-1].isdigit():
        trimmed = parts[:-1]
    return " ".join(word.capitalize() for word in trimmed)


def _normalize_header(cell: str) -> str:
    return re.sub(r"\s+", " ", cell.replace("<br>", " ").strip()).lower()


def _find_prior_value_key(fieldnames: list[str]) -> str:
    for key in fieldnames:
        norm = _normalize_header(key)
        if norm.startswith("value as of"):
            return key
    raise ValueError("Could not find prior value column (expected 'Value as of …')")


def _parse_float(raw: str) -> float | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _clean_holding_name(name: str) -> str:
    """Strip fund-export markers (^^, ‡, **, ^^^, $$~~) for stock identity and NSE lookup."""
    text = (name or "").strip()
    if text.startswith("^^"):
        text = text[2:].strip()
    text = re.sub(r"‡", "", text)
    text = text.replace("$$~~", "").replace("~~", "")
    text = re.sub(r"\$+", "", text)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\^+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+A$", "", text)
    return text.strip()


def canonical_holding_display_name(names: list[str]) -> str:
    """Pick one label when funds use different spellings (Ltd. vs Limited, etc.)."""
    cleaned = [_clean_holding_name(n) for n in names if (n or "").strip()]
    if not cleaned:
        return ""
    return max(cleaned, key=lambda n: (len(n), n.lower()))


def stock_key(nse: str, bse: str, name: str) -> str:
    from mf_screener.symbol_map import normalize_company_name

    nse = (nse or "").strip()
    bse = (bse or "").strip()
    name = _clean_holding_name(name)
    if nse:
        return f"NSE:{nse.upper()}"
    if bse:
        return f"BSE:{bse.upper()}"
    norm = normalize_company_name(name)
    return f"NAME:{norm}" if norm else "NAME:"


def load_holdings_from_folder(folder: Path) -> list[HoldingRow]:
    rows: list[HoldingRow] = []
    for path in discover_csv_paths(folder):
        rows.extend(load_fund_csv(path))
    return rows


def _parse_cell(raw: str) -> float | None:
    raw = (raw or "").strip()
    if not raw or raw == "-":
        return None
    return _parse_float(raw)


def _share_change_from_counts(
    current_shares: float | None, prior_shares: float | None
) -> tuple[str, float | None]:
    if prior_shares is None or prior_shares <= 0:
        if current_shares is not None and current_shares > 0:
            return "New", current_shares
        return "", None
    if current_shares is None or current_shares <= 0:
        return str(-100.0), -(prior_shares)
    delta = current_shares - prior_shares
    if delta == 0:
        return "0", 0.0
    pct = (delta / prior_shares) * 100.0
    return str(round(pct, 6)), delta


def _is_equity_holdings_export(line: str) -> bool:
    return "equity holdings" in (line or "").strip().lower()


def _read_until_equity_or_header(path: Path) -> tuple[str | None, list[str]]:
    """Return (format, remaining_lines). format is 'equity' or 'trendlyne'."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        lines = f.readlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return None, []
    if _is_equity_holdings_export(lines[0]):
        return "equity", lines[1:]
    return "trendlyne", lines


def load_fund_csv(path: Path) -> list[HoldingRow]:
    slug = slug_from_filename(path)
    display = display_name_from_slug(slug)
    fmt, lines = _read_until_equity_or_header(path)
    if fmt == "equity":
        return _load_equity_holdings_lines(lines, slug, display)
    if fmt == "trendlyne":
        return _load_trendlyne_lines(lines, slug, display)
    return []


def _load_trendlyne_lines(lines: list[str], slug: str, display: str) -> list[HoldingRow]:
    out: list[HoldingRow] = []
    reader = csv.DictReader(lines)
    if not reader.fieldnames:
        return out
    prior_key = _find_prior_value_key(list(reader.fieldnames))
    for raw in reader:
        row = _dict_row_to_holding(raw, prior_key, slug, display)
        if row is not None:
            out.append(row)
    return out


def _load_equity_holdings_lines(lines: list[str], slug: str, display: str) -> list[HoldingRow]:
    """Multi-month export: current month = first pair, previous = second pair."""
    out: list[HoldingRow] = []
    if len(lines) < 2:
        return out
    reader = csv.reader(lines[1:])
    next(reader, None)  # skip sub-header row (% of AUM, No. of Shares, ...)
    for row in reader:
        if not row or not (row[0] or "").strip():
            continue
        name = _clean_holding_name(row[0].strip())
        if len(row) < 5:
            continue
        current_weight = _parse_cell(row[1])
        current_shares = _parse_cell(row[2])
        prior_weight = _parse_cell(row[3])
        prior_shares = _parse_cell(row[4])
        if current_weight is None and current_shares is None:
            continue
        if current_weight is None:
            current_weight = 0.0
        share_raw, share_abs = _share_change_from_counts(current_shares, prior_shares)
        out.append(
            HoldingRow(
                fund_slug=slug,
                fund_display_name=display,
                name=name,
                nse="",
                bse="",
                sector="",
                current_value=1.0,
                prior_value=1.0,
                current_weight_pct=current_weight,
                quantity=current_shares,
                share_change_abs=share_abs,
                share_change_raw=share_raw,
                history_url="",
                prior_weight_pct=prior_weight,
            )
        )
    return out


def _dict_row_to_holding(
    raw: dict[str, Any],
    prior_key: str,
    slug: str,
    display: str,
) -> HoldingRow | None:
    name = _clean_holding_name(raw.get("Invested In") or "")
    if not name:
        return None

    current_weight = _parse_float(raw.get("% of Total Holding", ""))
    current_value = _parse_float(raw.get("Market Value Latest Price", ""))
    prior_value = _parse_float(raw.get(prior_key, ""))
    if current_weight is None or current_value is None or prior_value is None:
        return None

    share_raw = (raw.get("Month Change <br> in Shares %") or "").strip()
    if not share_raw:
        share_raw = (raw.get("Month Change  in Shares %") or "").strip()

    share_abs_raw = (raw.get("Month Change <br> in Shares") or "").strip()
    if not share_abs_raw:
        share_abs_raw = (raw.get("Month Change  in Shares") or "").strip()

    return HoldingRow(
        fund_slug=slug,
        fund_display_name=display,
        name=name,
        nse=(raw.get("NSE Code") or "").strip(),
        bse=(raw.get("BSE Code") or "").strip(),
        sector=(raw.get("Sector") or "").strip(),
        current_value=current_value,
        prior_value=prior_value,
        current_weight_pct=current_weight,
        quantity=_parse_float(raw.get("Quantity", "")),
        share_change_abs=_parse_float(share_abs_raw),
        share_change_raw=share_raw,
        history_url=(raw.get("History ") or raw.get("History") or "").strip(),
    )


def iter_fund_groups(rows: list[HoldingRow]) -> Iterator[tuple[str, list[HoldingRow]]]:
    by_fund: dict[str, list[HoldingRow]] = {}
    for row in rows:
        by_fund.setdefault(row.fund_slug, []).append(row)
    for slug in sorted(by_fund):
        yield slug, by_fund[slug]
