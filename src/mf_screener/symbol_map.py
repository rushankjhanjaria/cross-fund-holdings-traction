"""Company name to NSE symbol map for price enrichment."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

NAME_TO_NSE_PATH = Path(__file__).resolve().parents[2] / "config" / "name_to_nse.csv"


@dataclass(frozen=True)
class ListedSymbol:
    """Exchange listing code for yfinance (NSE → .NS, BSE → .BO)."""

    code: str
    exchange: str = "NSE"


def normalize_company_name(name: str) -> str:
    """Normalize holding/map names for lookup (fund CSV style vs NSE master)."""
    text = (name or "").strip().lower()
    if text.startswith("^^"):
        text = text[2:].strip()
    text = re.sub(r"\s+", " ", text)
    for ch in ".'`":
        text = text.replace(ch, "")
    text = text.replace("-", " ")
    text = text.replace("&", " and ")
    text = re.sub(r"\bcoltd\b", " ltd", text)
    text = re.sub(r"\bpvt\b", " private", text)
    text = re.sub(r"\((i|india)\)", "india", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text.startswith("the "):
        text = text[4:].strip()
    for suffix in (
        " limited",
        " ltd",
        " private",
        " ordinary shares",
        " india",
        " (india)",
    ):
        while text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    text = re.sub(r"\bcompany\b", "co", text)
    text = re.sub(r"\bco\b", "", text)
    if text.endswith(" service"):
        text = text[: -len(" service")] + " services"
    if text.endswith(" system"):
        text = text[: -len(" system")] + " systems"
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_company_name_compact(name: str) -> str:
    """Same as normalize_company_name but with spaces removed (Black Buck vs BLACKBUCK)."""
    return normalize_company_name(name).replace(" ", "")


def _listed_from_row(row: dict[str, str]) -> ListedSymbol | None:
    code = (row.get("nse") or "").strip().upper()
    if not code:
        return None
    exchange = (row.get("exchange") or "NSE").strip().upper()
    if exchange in ("NS", "NSE"):
        exchange = "NSE"
    elif exchange in ("BO", "BSE"):
        exchange = "BSE"
    return ListedSymbol(code=code, exchange=exchange)


def load_name_to_nse(path: Path | None = None) -> dict[str, ListedSymbol]:
    """Load map normalized_name -> listing code (NSE or BSE)."""
    path = path or NAME_TO_NSE_PATH
    if not path.is_file():
        return {}

    mapping: dict[str, ListedSymbol] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return mapping
        for row in reader:
            name = (row.get("company_name") or row.get("name") or "").strip()
            listed = _listed_from_row(row)
            if name and listed:
                mapping[normalize_company_name(name)] = listed
                compact = normalize_company_name_compact(name)
                mapping.setdefault(compact, listed)
    return mapping


def resolve_nse(
    *,
    name: str,
    nse_from_row: str,
    name_map: dict[str, ListedSymbol],
) -> ListedSymbol | None:
    if (nse_from_row or "").strip():
        return ListedSymbol(code=nse_from_row.strip().upper(), exchange="NSE")
    key = normalize_company_name(name)
    hit = name_map.get(key)
    if hit:
        return hit
    return name_map.get(normalize_company_name_compact(name))
