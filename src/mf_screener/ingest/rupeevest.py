"""Download MF portfolio CSVs from RupeeVest Portfolio Tracker (HTTP API).

One path: resolve name → skip existing CSV (unless overwrite) → fetch tracker
→ write CSV. No API disk cache — ingest volume is low.
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

BASE_URL = "https://www.rupeevest.com"
SEARCH_PATH = "/home/get_search_data"
TRACKER_PATH = "/home/get_mf_portfolio_tracker"
USER_AGENT = "Mozilla/5.0 (compatible; mf-screener/1.0; +https://github.com/)"
_HTTP_RETRIES = 1
_HTTP_RETRY_BASE_SLEEP = 0.5

_MONTH_TO_NUM = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class FundSearchIndex:
    """RupeeVest display name -> scheme code."""

    by_exact_name: dict[str, str]
    by_lower_name: dict[str, str]
    collisions: tuple[str, ...] = ()

    @classmethod
    def from_mapping(
        cls,
        by_exact_name: dict[str, str],
        *,
        collisions: list[str] | None = None,
    ) -> FundSearchIndex:
        return cls(
            by_exact_name=by_exact_name,
            by_lower_name={name.lower(): name for name in by_exact_name},
            collisions=tuple(collisions or ()),
        )

    def resolve(self, query: str) -> tuple[str, str] | None:
        """Return (canonical_name, schemecode) or None."""
        q = (query or "").strip()
        if not q:
            return None
        if q in self.by_exact_name:
            return q, self.by_exact_name[q]
        hit = self.by_lower_name.get(q.lower())
        if hit:
            return hit, self.by_exact_name[hit]
        tokens = _TOKEN_RE.findall(q.lower())
        if not tokens:
            return None
        candidates: list[tuple[int, str]] = []
        for name in self.by_exact_name:
            if all(_token_in_name(name.lower(), t) for t in tokens):
                candidates.append((len(name), name))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        best = candidates[0][1]
        return best, self.by_exact_name[best]


def _token_in_name(name_l: str, token: str) -> bool:
    """Whole-token match so 'cap' does not hit 'capital'."""
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", name_l) is not None


def _http_get_json(path: str, *, params: dict[str, str] | None = None) -> Any:
    url = BASE_URL + path
    if params:
        url += "?" + urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    last_error: BaseException | None = None
    for attempt in range(_HTTP_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code >= 500 and attempt < _HTTP_RETRIES:
                time.sleep(_HTTP_RETRY_BASE_SLEEP * (attempt + 1))
                continue
            raise
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt < _HTTP_RETRIES:
                time.sleep(_HTTP_RETRY_BASE_SLEEP * (attempt + 1))
                continue
            raise
    assert last_error is not None
    raise last_error


def index_from_search_payload(data: dict[str, Any]) -> FundSearchIndex:
    """Build index from raw ``get_search_data`` JSON (single merge path)."""
    by_name: dict[str, str] = {}
    collisions: list[str] = []
    for key in ("search_data", "search_data_nfo"):
        for item in data.get(key) or []:
            name = (item.get("s_name1") or "").strip()
            code = str(item.get("schemecode") or "").strip()
            if not name or not code:
                continue
            existing = by_name.get(name)
            if existing is not None and existing != code:
                collisions.append(f"{name}: kept {existing}, ignored {code} ({key})")
                continue
            by_name[name] = code
    return FundSearchIndex.from_mapping(by_name, collisions=collisions)


def load_search_index() -> FundSearchIndex:
    data = _http_get_json(SEARCH_PATH)
    if not isinstance(data, dict):
        raise ValueError("RupeeVest search index response was not a JSON object")
    return index_from_search_payload(data)


def fetch_portfolio_tracker(schemecode: str) -> dict[str, Any]:
    data = _http_get_json(TRACKER_PATH, params={"schemecode": schemecode})
    if not isinstance(data, dict):
        raise ValueError(f"RupeeVest tracker response for {schemecode!r} was not a JSON object")
    return data


def _format_aum_cr(raw: str | float | int | None) -> str:
    if raw is None or raw == "-":
        return "-"
    try:
        val = float(str(raw).replace(",", ""))
    except ValueError:
        return str(raw)
    return f"{val:.1f}"


def _month_suffix(month_label: str) -> str:
    """Jun-26 -> 06_26."""
    m = re.match(r"^([A-Za-z]{3})-(\d{2})$", (month_label or "").strip())
    if not m:
        return "unknown"
    mon = _MONTH_TO_NUM.get(m.group(1).lower(), "00")
    return f"{mon}_{m.group(2)}"


def fund_slug_prefix(fund_name: str) -> str:
    """Filename stem without month suffix (``abakkus_small_cap``)."""
    text = (fund_name or "").strip()
    text = re.sub(r"-Reg\([^)]+\)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+Fund\s*$", "", text, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def default_output_slug(fund_name: str, lead_month: str) -> str:
    """Filename stem aligned with existing funds/june/*_06_26.csv pattern."""
    return f"{fund_slug_prefix(fund_name)}_{_month_suffix(lead_month)}"


def _existing_csv(out_dir: Path, fund_name: str, slug: str | None) -> Path | None:
    """Find an on-disk CSV for this fund without calling the tracker API."""
    if slug:
        path = out_dir / f"{slug}.csv"
        return path if path.is_file() else None
    prefix = fund_slug_prefix(fund_name)
    if not prefix:
        return None
    matches = sorted(out_dir.glob(f"{prefix}_*.csv"))
    return matches[0] if matches else None


def _pivot_holdings(
    stock_data: list[list[dict[str, Any]]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    aum: dict[str, list[str]] = {}
    shares: dict[str, list[str]] = {}
    months = len(stock_data)
    for month_idx, month_rows in enumerate(stock_data):
        for item in month_rows:
            fincode = str(item.get("fincode", ""))
            if not fincode:
                continue
            if fincode not in aum:
                aum[fincode] = ["-"] * months
                shares[fincode] = ["-"] * months
            aum[fincode][month_idx] = str(item.get("percent_aum", "-"))
            share_val = item.get("noshares", "-")
            shares[fincode][month_idx] = "-" if share_val is None else str(share_val)
    return aum, shares


def _cell_text(value: str | float | int | None) -> str:
    if value is None or value == "":
        return "-"
    text = str(value).strip()
    return "-" if text == "" else text


def portfolio_tracker_to_csv_text(data: dict[str, Any]) -> str:
    """Build RupeeVest-compatible equity holdings CSV (what the site Download exports)."""
    month_names: list[str] = list(data.get("month_name") or [])
    month_aums: list[dict[str, Any]] = list(data.get("MonthwiseAUM") or [])
    stock_data = list(data.get("stock_data") or [])
    stock_mapping = {str(k): v for k, v in (data.get("stock_mapping") or {}).items()}
    aum_by_code, shares_by_code = _pivot_holdings(stock_data)
    month_aum_fmt = [_format_aum_cr(m.get("aum")) for m in month_aums]

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([])
    writer.writerow(["Equity Holdings"])
    header = ["Company"]
    for idx, label in enumerate(month_names):
        header.append(f"{label} AUM:₹{month_aum_fmt[idx]}(Cr.)")
        header.append("")
    writer.writerow(header)
    writer.writerow([""] + ["% of AUM", "No. of Shares"] * len(month_names))

    def sort_key(fincode: str) -> tuple[float, str]:
        first = aum_by_code[fincode][0]
        try:
            weight = float(first)
        except ValueError:
            weight = -1.0
        return (-weight, stock_mapping.get(fincode, fincode).lower())

    for fincode in sorted(aum_by_code.keys(), key=sort_key):
        row: list[str] = [stock_mapping.get(fincode, fincode)]
        for i in range(len(month_names)):
            row.append(_cell_text(aum_by_code[fincode][i]))
            row.append(_cell_text(shares_by_code[fincode][i]))
        writer.writerow(row)
    return buf.getvalue()


@dataclass
class DownloadResult:
    query: str
    fund_name: str
    schemecode: str
    path: Path | None
    error: str | None = None

    @classmethod
    def failed(
        cls,
        *,
        query: str,
        error: str,
        fund_name: str = "",
        schemecode: str = "",
        path: Path | None = None,
    ) -> DownloadResult:
        return cls(
            query=query,
            fund_name=fund_name,
            schemecode=schemecode,
            path=path,
            error=error,
        )


def download_fund_csv(
    *,
    fund_query: str,
    out_dir: Path,
    index: FundSearchIndex,
    slug: str | None = None,
    overwrite: bool = False,
) -> DownloadResult:
    """Resolve fund → skip existing CSV → fetch tracker → write CSV."""
    resolved = index.resolve(fund_query)
    if not resolved:
        return DownloadResult.failed(
            query=fund_query,
            error="no matching fund on RupeeVest (check exact name)",
        )
    fund_name, schemecode = resolved

    if not overwrite:
        existing = _existing_csv(out_dir, fund_name, slug)
        if existing is not None:
            return DownloadResult.failed(
                query=fund_query,
                fund_name=fund_name,
                schemecode=schemecode,
                path=existing,
                error=f"exists (use --overwrite): {existing.name}",
            )

    try:
        payload = fetch_portfolio_tracker(schemecode)
    except urllib.error.HTTPError as exc:
        return DownloadResult.failed(
            query=fund_query,
            fund_name=fund_name,
            schemecode=schemecode,
            error=f"HTTP {exc.code}",
        )
    except urllib.error.URLError as exc:
        return DownloadResult.failed(
            query=fund_query,
            fund_name=fund_name,
            schemecode=schemecode,
            error=str(exc.reason),
        )

    months = list(payload.get("month_name") or [])
    lead_month = months[0] if months else "unknown"
    stem = slug or default_output_slug(fund_name, lead_month)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stem}.csv"
    path.write_text(portfolio_tracker_to_csv_text(payload), encoding="utf-8")
    return DownloadResult(
        query=fund_query,
        fund_name=fund_name,
        schemecode=schemecode,
        path=path,
        error=None,
    )
