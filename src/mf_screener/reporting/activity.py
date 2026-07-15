"""Fund-level CSV/HTML activity labels and stock-level signal rules."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TypeVar

from mf_screener.aggregate import FundContribution, StockAggregate

FundCsvActivity = Literal["increase", "decrease", "closed", "new", "hold"]

ADD_ACTIVITIES = frozenset({"increase", "new"})
REDUCE_ACTIVITIES = frozenset({"decrease", "closed"})
HOLD_ACTIVITIES = frozenset({"hold"})
ACTIONABLE_ACTIVITIES = frozenset({"increase", "decrease", "closed", "new"})

T = TypeVar("T")


def fund_csv_activity(fund: FundContribution) -> FundCsvActivity | None:
    """Map fund row to report activity label; None = omit from CSV/HTML."""
    if fund.is_new:
        return "new"
    if fund.share_change_pct is not None:
        if fund.share_change_pct > 0:
            return "increase"
        if fund.share_change_pct < 0:
            if fund.current_weight_pct < 0.05:
                return "closed"
            return "decrease"
        if fund.current_weight_pct > 0:
            return "hold"
        return None
    if fund.activity == "exit":
        if fund.current_weight_pct < 0.05:
            return "closed"
        return "decrease"
    if fund.activity == "hold" and fund.current_weight_pct > 0:
        return "hold"
    return None


def stock_has_actionable_fund_activity(stock: StockAggregate) -> bool:
    """True if at least one fund bought, sold, closed, or newly entered the stock."""
    for fund in stock.funds:
        activity = fund_csv_activity(fund)
        if activity in ACTIONABLE_ACTIVITIES:
            return True
    return False


def is_mixed_signal(add_count: int, reduce_count: int, hold_count: int) -> bool:
    """Funds disagree: two or more kinds among adding / reducing / unchanged."""
    kinds = sum(
        [
            add_count > 0,
            reduce_count > 0,
            hold_count > 0,
        ]
    )
    return kinds >= 2


def append_activity_line(
    buckets: tuple[list[T], list[T], list[T]],
    activity: str,
    line: T,
) -> None:
    adds, reduces, holds = buckets
    if activity in ADD_ACTIVITIES:
        adds.append(line)
    elif activity in REDUCE_ACTIVITIES:
        reduces.append(line)
    elif activity in HOLD_ACTIVITIES:
        holds.append(line)


def bucket_fund_contributions(
    funds: list[FundContribution],
    line_builder: Callable[[FundContribution, FundCsvActivity], T],
) -> tuple[list[T], list[T], list[T]]:
    adds: list[T] = []
    reduces: list[T] = []
    holds: list[T] = []
    buckets = (adds, reduces, holds)
    for fund in funds:
        activity = fund_csv_activity(fund)
        if activity is None:
            continue
        append_activity_line(buckets, activity, line_builder(fund, activity))
    return adds, reduces, holds
