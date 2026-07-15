"""Terminal tree output for CLI."""

from __future__ import annotations

from mf_screener.aggregate import FundContribution, StockAggregate


def _format_share(c: FundContribution) -> str:
    if c.is_new:
        return "shares New"
    if c.share_change_pct is None:
        return "shares —"
    sign = "+" if c.share_change_pct >= 0 else ""
    return f"shares {sign}{c.share_change_pct:.1f}%"


def _format_weight(c: FundContribution) -> str:
    if c.weight_delta_pp is None:
        return "weight —"
    sign = "+" if c.weight_delta_pp >= 0 else ""
    return f"weight {sign}{c.weight_delta_pp:.2f}pp"


def _format_median_share(value: float | None, new_count: int = 0) -> str:
    if value is not None:
        sign = "+" if value >= 0 else ""
        return f"median shares {sign}{value:.1f}%"
    if new_count:
        return f"median shares New ({new_count} funds)"
    return "median shares —"


def _format_median_weight(value: float | None) -> str:
    if value is None:
        return "median weight —"
    sign = "+" if value >= 0 else ""
    return f"median weight {sign}{value:.2f}pp"


def print_tree(stocks: list[StockAggregate], *, top: int | None) -> None:
    shown = stocks[:top] if top else stocks
    for stock in shown:
        label = stock.name
        if stock.nse:
            label = f"{stock.name} ({stock.nse})"
        header = (
            f"{label} — {stock.direction} | score={stock.score:.1f} | "
            f"{_format_median_share(stock.median_share_change_pct, stock.new_entry_count)} | "
            f"{stock.breadth_active} funds active | "
            f"{_format_median_weight(stock.median_weight_delta_pp)}"
        )
        print(header)
        for fund in stock.funds:
            if fund.activity == "hold" and fund.weight_delta_pp is None:
                continue
            if fund.activity == "hold" and fund.weight_delta_pp is not None:
                if abs(fund.weight_delta_pp) < 0.005:
                    continue
            line = f"  - {fund.fund_display_name} — {_format_share(fund)} | {_format_weight(fund)}"
            print(line)
        print()
