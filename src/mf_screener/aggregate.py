"""Aggregate holdings across funds and compute traction scores."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Literal

from mf_screener.metrics import FundStockMetrics
from mf_screener.load import canonical_holding_display_name

RankMode = Literal["composite", "share_activity", "mean_weight_delta", "new_entries"]
Direction = Literal["increase", "decrease", "mixed", "hold"]


@dataclass
class FundContribution:
    fund_slug: str
    fund_display_name: str
    share_change_pct: float | None
    share_change_abs: float | None
    weight_delta_pp: float | None
    current_weight_pct: float
    is_new: bool
    activity: str
    history_url: str


@dataclass
class StockAggregate:
    stock_key: str
    name: str
    nse: str
    bse: str
    sector: str
    direction: Direction
    score: float
    median_share_change_pct: float | None
    breadth_active: int
    median_weight_delta_pp: float | None
    breadth_weight_up: int
    new_entry_count: int
    fund_count: int
    funds: list[FundContribution] = field(default_factory=list)


DEFAULT_WEIGHT_SCALE = 10.0
DEFAULT_NEW_BOOST = 50.0


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.median(values)


def _direction(
    breadth_active: int,
    breadth_exit: int,
    median_share: float | None,
    median_weight: float | None,
) -> Direction:
    if breadth_active > 0 and breadth_exit == 0:
        return "increase"
    if breadth_exit > 0 and breadth_active == 0:
        return "decrease"
    if breadth_active > 0 and breadth_exit > 0:
        return "mixed"
    if median_weight is not None and median_weight > 0.01:
        return "increase"
    if median_weight is not None and median_weight < -0.01:
        return "decrease"
    return "hold"


def composite_score(
    breadth_active: int,
    median_share: float | None,
    breadth_weight_up: int,
    median_weight: float | None,
    new_entry_count: int,
    *,
    weight_scale: float = DEFAULT_WEIGHT_SCALE,
    new_boost: float = DEFAULT_NEW_BOOST,
) -> float:
    share_term = 0.0
    if median_share is not None and breadth_active > 0:
        share_term = breadth_active * median_share

    weight_term = 0.0
    if median_weight is not None and breadth_weight_up > 0:
        weight_term = breadth_weight_up * median_weight * weight_scale

    return share_term + weight_term + new_entry_count * new_boost


def share_activity_score(breadth_active: int, median_share: float | None) -> float:
    if median_share is None or breadth_active == 0:
        return 0.0
    return breadth_active * median_share


def aggregate_by_stock(
    metrics: list[FundStockMetrics],
    *,
    rank_mode: RankMode = "composite",
    weight_scale: float = DEFAULT_WEIGHT_SCALE,
    new_boost: float = DEFAULT_NEW_BOOST,
) -> list[StockAggregate]:
    by_stock: dict[str, list[FundStockMetrics]] = {}
    for m in metrics:
        by_stock.setdefault(m.stock_key, []).append(m)

    results: list[StockAggregate] = []

    for key, fund_rows in by_stock.items():
        sample = fund_rows[0]
        display_name = canonical_holding_display_name([m.name for m in fund_rows])
        contributions: list[FundContribution] = []

        share_for_median: list[float] = []
        weights: list[float] = []
        breadth_active = 0
        breadth_exit = 0
        breadth_weight_up = 0
        new_entry_count = 0

        for m in fund_rows:
            contributions.append(
                FundContribution(
                    fund_slug=m.fund_slug,
                    fund_display_name=m.fund_display_name,
                    share_change_pct=m.share_change_pct,
                    share_change_abs=m.share_change_abs,
                    weight_delta_pp=m.weight_delta_pp,
                    current_weight_pct=m.current_weight_pct,
                    is_new=m.is_new,
                    activity=m.activity,
                    history_url=m.history_url,
                )
            )

            if m.is_new:
                new_entry_count += 1
                breadth_active += 1
            elif m.share_change_pct is not None:
                if m.share_change_pct > 0:
                    breadth_active += 1
                    share_for_median.append(m.share_change_pct)
                elif m.share_change_pct < 0:
                    breadth_exit += 1
                    share_for_median.append(m.share_change_pct)

            if m.weight_delta_pp is not None:
                weights.append(m.weight_delta_pp)
                if m.weight_delta_pp > 0:
                    breadth_weight_up += 1

        median_share = _median(share_for_median)
        median_weight = _median(weights)
        direction = _direction(breadth_active, breadth_exit, median_share, median_weight)

        if rank_mode == "composite":
            score = composite_score(
                breadth_active,
                median_share,
                breadth_weight_up,
                median_weight,
                new_entry_count,
                weight_scale=weight_scale,
                new_boost=new_boost,
            )
        elif rank_mode == "share_activity":
            score = share_activity_score(breadth_active, median_share)
        elif rank_mode == "mean_weight_delta":
            score = statistics.mean(weights) if weights else 0.0
        elif rank_mode == "new_entries":
            score = float(new_entry_count)
        else:
            score = 0.0

        contributions.sort(
            key=lambda c: (
                0 if c.is_new else 1,
                -(c.share_change_pct or 0),
                -(c.weight_delta_pp or 0),
            ),
        )

        results.append(
            StockAggregate(
                stock_key=key,
                name=display_name,
                nse=sample.nse,
                bse=sample.bse,
                sector=sample.sector,
                direction=direction,
                score=score,
                median_share_change_pct=median_share,
                breadth_active=breadth_active,
                median_weight_delta_pp=median_weight,
                breadth_weight_up=breadth_weight_up,
                new_entry_count=new_entry_count,
                fund_count=len(fund_rows),
                funds=contributions,
            )
        )

    results.sort(key=lambda s: (-s.score, -(s.median_share_change_pct or 0), s.name))
    return results
