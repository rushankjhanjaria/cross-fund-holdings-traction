"""Shared display formatting for CSV and HTML reports."""

from __future__ import annotations

from typing import Any

from mf_screener.aggregate import FundContribution, StockAggregate

_EMPTY_SNAKE = {
    "month_high": "",
    "month_low": "",
    "estimated_entry_mid": "",
    "month_end_close": "",
    "sma_30": "",
    "close_latest": "",
    "pct_vs_entry_mid": "",
    "pct_vs_sma": "",
}


def format_share_pct_change(fund: FundContribution) -> str:
    if fund.is_new:
        return "New"
    if fund.share_change_pct is None:
        if fund.activity == "hold":
            return "0%"
        return ""
    if fund.share_change_pct == 0:
        return "0%"
    sign = "+" if fund.share_change_pct > 0 else ""
    return f"{sign}{fund.share_change_pct:.2f}%"


def format_pct_of_aum(fund: FundContribution) -> str:
    return f"{fund.current_weight_pct:.2f}%"


def stock_csv_direction(stock: StockAggregate) -> str:
    if stock.direction in ("increase", "decrease"):
        return stock.direction
    if stock.direction == "mixed":
        return "mixed"
    return "hold"


def direction_label_from_aggregate(direction: str) -> str:
    """Map JSON report direction string to HTML stockDirection."""
    d = (direction or "hold").strip().lower()
    if d in ("increase", "decrease", "mixed"):
        return d
    return "hold"


def _fmt_price_value(val: object) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.4f}".rstrip("0").rstrip(".")
    return str(val)


def primary_pct_vs(est_or_stock: dict[str, Any] | None) -> str:
    """Prefer pct vs 30d SMA; fall back to legacy vs entry mid."""
    if not est_or_stock:
        return ""
    for key in ("pct_vs_sma", "pctVsSma", "pct_vs_entry_mid", "pctVsMid"):
        raw = est_or_stock.get(key)
        if raw not in ("", None):
            return _fmt_price_value(raw) if not isinstance(raw, str) else raw
    return ""


def entry_price_fields_snake(est: dict | None) -> dict[str, str]:
    if not est or est.get("status") != "ok":
        return dict(_EMPTY_SNAKE)
    return {
        "month_high": _fmt_price_value(est.get("month_high")),
        "month_low": _fmt_price_value(est.get("month_low")),
        "estimated_entry_mid": _fmt_price_value(est.get("estimated_entry_mid")),
        "month_end_close": _fmt_price_value(est.get("month_end_close")),
        "sma_30": _fmt_price_value(est.get("sma_30")),
        "close_latest": _fmt_price_value(est.get("close_latest")),
        "pct_vs_entry_mid": _fmt_price_value(est.get("pct_vs_entry_mid")),
        "pct_vs_sma": _fmt_price_value(est.get("pct_vs_sma")),
    }


def entry_price_fields_camel(est: dict | None) -> dict[str, str]:
    snake = entry_price_fields_snake(est)
    pct_primary = snake["pct_vs_sma"] or snake["pct_vs_entry_mid"]
    return {
        "monthHigh": snake["month_high"],
        "monthLow": snake["month_low"],
        "entryMid": snake["estimated_entry_mid"],
        "monthEndClose": snake["month_end_close"],
        "sma30": snake["sma_30"],
        "closeLatest": snake["close_latest"],
        # pctVsMid kept as alias of primary (SMA) for older clients
        "pctVsMid": pct_primary,
        "pctVsSma": snake["pct_vs_sma"],
    }


def entry_price_fields_camel_from_csv_row(row: dict[str, str]) -> dict[str, str]:
    """Build HTML camel price fields from a flat CSV row (fallback path)."""
    est = {
        "status": "ok" if (row.get("close_latest") or row.get("sma_30")) else "missing",
        "month_high": row.get("month_high") or "",
        "month_low": row.get("month_low") or "",
        "estimated_entry_mid": row.get("estimated_entry_mid") or "",
        "month_end_close": row.get("month_end_close") or "",
        "sma_30": row.get("sma_30") or "",
        "close_latest": row.get("close_latest") or "",
        "pct_vs_entry_mid": row.get("pct_vs_entry_mid") or "",
        "pct_vs_sma": row.get("pct_vs_sma") or "",
    }
    if est["status"] != "ok":
        return entry_price_fields_camel(None)
    return entry_price_fields_camel(est)


def entry_csv_fields_for_stock(
    stock: StockAggregate,
    entry_by_stock_key: dict[str, dict] | None,
) -> dict[str, str]:
    if not entry_by_stock_key:
        return dict(_EMPTY_SNAKE)
    est = entry_by_stock_key.get(stock.stock_key)
    return entry_price_fields_snake(est if isinstance(est, dict) else None)
