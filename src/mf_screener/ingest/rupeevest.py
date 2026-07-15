"""Download MF portfolio CSVs from RupeeVest Portfolio Tracker (HTTP API)."""

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
USER_AGENT = (
    "Mozilla/5.0 (compatible; mf-screener/1.0; +https://github.com/)"
)

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


@dataclass(frozen=True)
class FundSearchIndex:
    """RupeeVest display name -> scheme code."""

    by_exact_name: dict[str, str]
    canonical_names: list[str]

    def resolve(self, query: str) -> tuple[str, str] | None:
        """Return (canonical_name, schemecode) or None."""
        q = (query or "").strip()
        if not q:
            return None
        if q in self.by_exact_name:
            return q, self.by_exact_name[q]
        lower_map = {name.lower(): name for name in self.by_exact_name}
        hit = lower_map.get(q.lower())
        if hit:
            return hit, self.by_exact_name[hit]
        tokens = [t for t in re.split(r"\s+", q.lower()) if t]
        if not tokens:
            return None
        candidates: list[tuple[int, str]] = []
        for name in self.canonical_names:
            name_l = name.lower()
            if all(t in name_l for t in tokens):
                candidates.append((len(name), name))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        best = candidates[0][1]
        return best, self.by_exact_name[best]


def _http_get_json(path: str, *, params: dict[str, str] | None = None) -> Any:
    url = BASE_URL + path
    if params:
        url += "?" + urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "X-Robots-Tag": "noindex",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def load_search_index() -> FundSearchIndex:
    data = _http_get_json(SEARCH_PATH)
    by_name: dict[str, str] = {}
    for key in ("search_data", "search_data_nfo"):
        for item in data.get(key) or []:
            name = (item.get("s_name1") or "").strip()
            code = str(item.get("schemecode") or "").strip()
            if name and code:
                by_name[name] = code
    return FundSearchIndex(by_exact_name=by_name, canonical_names=sorted(by_name))


def fetch_portfolio_tracker(schemecode: str) -> dict[str, Any]:
    return _http_get_json(TRACKER_PATH, params={"schemecode": schemecode})


def _format_aum_cr(raw: str | float | int | None) -> str:
    if raw is None or raw == "-":
        return "-"
    try:
        val = float(str(raw).replace(",", ""))
    except ValueError:
        return str(raw)
    return f"{val:.1f}" if val == round(val, 1) else str(val)


def _month_suffix(month_label: str) -> str:
    """Jun-26 -> 06_26."""
    m = re.match(r"^([A-Za-z]{3})-(\d{2})$", (month_label or "").strip())
    if not m:
        return "unknown"
    mon = _MONTH_TO_NUM.get(m.group(1).lower(), "00")
    return f"{mon}_{m.group(2)}"


def default_output_slug(fund_name: str, lead_month: str) -> str:
    """Filename stem aligned with existing funds/june/*_06_26.csv pattern."""
    text = (fund_name or "").strip()
    text = re.sub(r"-Reg\([^)]+\)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+Fund\s*$", "", text, flags=re.IGNORECASE)
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return f"{slug}_{_month_suffix(lead_month)}"


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


def _write_equity_section(
    writer: csv.writer,
    *,
    month_names: list[str],
    month_aums: list[dict[str, Any]],
    stock_data: list[list[dict[str, Any]]],
    stock_mapping: dict[str, str],
) -> None:
    aum_by_code, shares_by_code = _pivot_holdings(stock_data)
    month_aum_fmt = [_format_aum_cr(m.get("aum")) for m in month_aums]

    writer.writerow([])
    writer.writerow(["Equity Holdings"])
    header = ["Company"]
    for idx, label in enumerate(month_names):
        header.append(f"{label} AUM:₹{month_aum_fmt[idx]}(Cr.)")
        header.append("")
    writer.writerow(header)

    sub = ["", "% of AUM", "No. of Shares"] * len(month_names)
    sub[0] = ""
    writer.writerow(sub)

    def sort_key(fincode: str) -> tuple[float, str]:
        first = aum_by_code[fincode][0]
        try:
            weight = float(first)
        except ValueError:
            weight = -1.0
        name = stock_mapping.get(fincode, fincode)
        return (-weight, name.lower())

    for fincode in sorted(aum_by_code.keys(), key=sort_key):
        name = stock_mapping.get(fincode, fincode)
        row: list[str] = [name]
        for i in range(len(month_names)):
            row.append(_cell_text(aum_by_code[fincode][i]))
            row.append(_cell_text(shares_by_code[fincode][i]))
        writer.writerow(row)


def portfolio_tracker_to_csv_text(data: dict[str, Any]) -> str:
    """Build RupeeVest-compatible equity holdings CSV (what the site Download exports)."""
    month_names: list[str] = list(data.get("month_name") or [])
    month_aums: list[dict[str, Any]] = list(data.get("MonthwiseAUM") or [])
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    _write_equity_section(
        writer,
        month_names=month_names,
        month_aums=month_aums,
        stock_data=list(data.get("stock_data") or []),
        stock_mapping={str(k): v for k, v in (data.get("stock_mapping") or {}).items()},
    )
    return buf.getvalue()


@dataclass
class DownloadResult:
    query: str
    fund_name: str
    schemecode: str
    path: Path | None
    error: str | None = None


def download_fund_csv(
    *,
    fund_query: str,
    out_dir: Path,
    index: FundSearchIndex,
    slug: str | None = None,
    overwrite: bool = False,
    delay_seconds: float = 0.0,
) -> DownloadResult:
    resolved = index.resolve(fund_query)
    if not resolved:
        return DownloadResult(
            query=fund_query,
            fund_name="",
            schemecode="",
            path=None,
            error="no matching fund on RupeeVest (check exact name)",
        )
    fund_name, schemecode = resolved
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    try:
        payload = fetch_portfolio_tracker(schemecode)
    except urllib.error.HTTPError as exc:
        return DownloadResult(
            query=fund_query,
            fund_name=fund_name,
            schemecode=schemecode,
            path=None,
            error=f"HTTP {exc.code}",
        )
    except urllib.error.URLError as exc:
        return DownloadResult(
            query=fund_query,
            fund_name=fund_name,
            schemecode=schemecode,
            path=None,
            error=str(exc.reason),
        )

    months = list(payload.get("month_name") or [])
    lead_month = months[0] if months else "unknown"
    stem = slug or default_output_slug(fund_name, lead_month)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stem}.csv"
    if path.exists() and not overwrite:
        return DownloadResult(
            query=fund_query,
            fund_name=fund_name,
            schemecode=schemecode,
            path=None,
            error=f"exists (use --overwrite): {path.name}",
        )

    csv_text = portfolio_tracker_to_csv_text(payload)
    path.write_text(csv_text, encoding="utf-8")
    return DownloadResult(
        query=fund_query,
        fund_name=fund_name,
        schemecode=schemecode,
        path=path,
        error=None,
    )
