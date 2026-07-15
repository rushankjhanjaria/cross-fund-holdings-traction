"""Shared display formatting for CSV and HTML reports."""

from __future__ import annotations

from mf_screener.aggregate import FundContribution, StockAggregate

_EMPTY_SNAKE = {
    "month_high": "",
    "month_low": "",
    "estimated_entry_mid": "",
    "close_latest": "",
    "pct_vs_entry_mid": "",
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


def entry_price_fields_snake(est: dict | None) -> dict[str, str]:
    if not est or est.get("status") != "ok":
        return dict(_EMPTY_SNAKE)
    return {
        "month_high": _fmt_price_value(est.get("month_high")),
        "month_low": _fmt_price_value(est.get("month_low")),
        "estimated_entry_mid": _fmt_price_value(est.get("estimated_entry_mid")),
        "close_latest": _fmt_price_value(est.get("close_latest")),
        "pct_vs_entry_mid": _fmt_price_value(est.get("pct_vs_entry_mid")),
    }


def entry_price_fields_camel(est: dict | None) -> dict[str, str]:
    snake = entry_price_fields_snake(est)
    return {
        "monthHigh": snake["month_high"],
        "monthLow": snake["month_low"],
        "entryMid": snake["estimated_entry_mid"],
        "closeLatest": snake["close_latest"],
        "pctVsMid": snake["pct_vs_entry_mid"],
    }


def entry_csv_fields_for_stock(
    stock: StockAggregate,
    entry_by_stock_key: dict[str, dict] | None,
) -> dict[str, str]:
    if not entry_by_stock_key:
        return dict(_EMPTY_SNAKE)
    est = entry_by_stock_key.get(stock.stock_key)
    return entry_price_fields_snake(est if isinstance(est, dict) else None)
