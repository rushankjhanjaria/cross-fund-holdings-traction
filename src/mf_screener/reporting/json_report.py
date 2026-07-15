"""JSON report document for --out."""

from __future__ import annotations

from pathlib import Path

from mf_screener.aggregate import StockAggregate


def stock_to_dict(stock: StockAggregate, *, entry_estimate: dict | None = None) -> dict:
    payload = {
        "stock_key": stock.stock_key,
        "name": stock.name,
        "nse": stock.nse,
        "bse": stock.bse,
        "sector": stock.sector,
        "direction": stock.direction,
        "score": round(stock.score, 4),
        "median_share_change_pct": stock.median_share_change_pct,
        "breadth_active": stock.breadth_active,
        "median_weight_delta_pp": stock.median_weight_delta_pp,
        "breadth_weight_up": stock.breadth_weight_up,
        "new_entry_count": stock.new_entry_count,
        "fund_count": stock.fund_count,
        "funds": [
            {
                "fund_slug": f.fund_slug,
                "fund_display_name": f.fund_display_name,
                "share_change_pct": f.share_change_pct,
                "share_change_abs": f.share_change_abs,
                "weight_delta_pp": f.weight_delta_pp,
                "current_weight_pct": f.current_weight_pct,
                "is_new": f.is_new,
                "activity": f.activity,
                "history_url": f.history_url,
            }
            for f in stock.funds
        ],
    }
    if entry_estimate is not None:
        payload["entry_estimate"] = entry_estimate
    return payload


def build_report(
    stocks: list[StockAggregate],
    *,
    folder: Path,
    rank: str,
    stock_count_total: int,
    include_holds: bool,
    price_month: str | None = None,
    entry_by_stock_key: dict[str, dict] | None = None,
) -> dict:
    reported = len(stocks)
    excluded = 0 if include_holds else stock_count_total - reported
    return {
        "folder": str(folder.resolve()),
        "rank_mode": rank,
        "include_holds": include_holds,
        "stock_count": reported,
        "stock_count_total": stock_count_total,
        "excluded_hold_count": excluded,
        "price_month": price_month,
        "stocks": [
            stock_to_dict(
                s,
                entry_estimate=(
                    entry_by_stock_key.get(s.stock_key)
                    if entry_by_stock_key is not None
                    else None
                ),
            )
            for s in stocks
        ],
    }
