"""Which stocks appear in JSON/CSV/HTML reports."""

from __future__ import annotations

from mf_screener.aggregate import StockAggregate
from mf_screener.reporting.activity import stock_has_actionable_fund_activity


def filter_for_report(
    stocks: list[StockAggregate],
    *,
    include_holds: bool,
) -> list[StockAggregate]:
    """Drop stocks where every fund only has unchanged share count (hold)."""
    active = [s for s in stocks if stock_has_actionable_fund_activity(s)]
    if not include_holds:
        return active
    seen = {s.stock_key for s in active}
    extra = [s for s in stocks if s.direction == "hold" and s.stock_key not in seen]
    return active + extra
