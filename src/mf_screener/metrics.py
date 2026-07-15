"""Per-holding and per-fund metrics: share activity and weight delta."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Literal

from mf_screener.load import HoldingRow, stock_key

ActivityKind = Literal["new", "active", "hold", "exit"]

NEW_SHARE_SENTINEL = 100.0


@dataclass(frozen=True)
class FundStockMetrics:
    fund_slug: str
    fund_display_name: str
    stock_key: str
    name: str
    nse: str
    bse: str
    sector: str
    current_weight_pct: float
    prior_weight_pct: float | None
    weight_delta_pp: float | None
    share_change_pct: float | None
    share_change_abs: float | None
    is_new: bool
    activity: ActivityKind
    history_url: str


def parse_share_change(raw: str) -> tuple[float | None, bool]:
    """Return (numeric_pct, is_new)."""
    raw = (raw or "").strip()
    if not raw:
        return None, False
    if raw.lower() == "new":
        return NEW_SHARE_SENTINEL, True
    try:
        return float(raw.replace(",", "")), False
    except ValueError:
        return None, False


def median_nav_from_fund(rows: list[HoldingRow]) -> float | None:
    estimates: list[float] = []
    for row in rows:
        if row.current_weight_pct <= 0:
            continue
        estimates.append(row.current_value / (row.current_weight_pct / 100.0))
    if not estimates:
        return None
    return statistics.median(estimates)


def classify_activity(share_pct: float | None, is_new: bool) -> ActivityKind:
    if is_new:
        return "new"
    if share_pct is None:
        return "hold"
    if share_pct > 0:
        return "active"
    if share_pct < 0:
        return "exit"
    return "hold"


def enrich_fund_holdings(rows: list[HoldingRow]) -> list[FundStockMetrics]:
    nav_median = median_nav_from_fund(rows)
    enriched: list[FundStockMetrics] = []

    for row in rows:
        share_pct, is_new = parse_share_change(row.share_change_raw)
        activity = classify_activity(share_pct if not is_new else None, is_new)

        prior_weight: float | None = None
        weight_delta: float | None = None
        if row.prior_weight_pct is not None:
            prior_weight = row.prior_weight_pct
            weight_delta = row.current_weight_pct - row.prior_weight_pct
        elif nav_median and nav_median > 0:
            prior_weight = (row.prior_value / nav_median) * 100.0
            weight_delta = row.current_weight_pct - prior_weight
            if is_new and weight_delta is not None and weight_delta < row.current_weight_pct:
                weight_delta = row.current_weight_pct

        enriched.append(
            FundStockMetrics(
                fund_slug=row.fund_slug,
                fund_display_name=row.fund_display_name,
                stock_key=stock_key(row.nse, row.bse, row.name),
                name=row.name,
                nse=row.nse,
                bse=row.bse,
                sector=row.sector,
                current_weight_pct=row.current_weight_pct,
                prior_weight_pct=prior_weight,
                weight_delta_pp=weight_delta,
                share_change_pct=share_pct if not is_new else None,
                share_change_abs=row.share_change_abs,
                is_new=is_new,
                activity=activity,
                history_url=row.history_url,
            )
        )
    return enriched


def enrich_all(rows: list[HoldingRow]) -> list[FundStockMetrics]:
    from mf_screener.load import iter_fund_groups

    out: list[FundStockMetrics] = []
    for _, fund_rows in iter_fund_groups(rows):
        out.extend(enrich_fund_holdings(fund_rows))
    return out
