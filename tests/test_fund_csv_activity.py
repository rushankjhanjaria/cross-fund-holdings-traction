from mf_screener.aggregate import FundContribution
from mf_screener.reporting.activity import (
    ACTIONABLE_ACTIVITIES,
    fund_csv_activity,
    stock_has_actionable_fund_activity,
)
from mf_screener.aggregate import StockAggregate


def _fund(**kwargs) -> FundContribution:
    defaults = dict(
        fund_slug="f",
        fund_display_name="Fund",
        share_change_pct=10.0,
        share_change_abs=100.0,
        weight_delta_pp=0.1,
        current_weight_pct=1.0,
        is_new=False,
        activity="active",
        history_url="",
    )
    defaults.update(kwargs)
    return FundContribution(**defaults)


def test_new_is_actionable() -> None:
    assert fund_csv_activity(_fund(is_new=True, share_change_pct=None)) == "new"


def test_hold_not_actionable() -> None:
    assert (
        fund_csv_activity(
            _fund(share_change_pct=0.0, activity="hold", current_weight_pct=1.0)
        )
        == "hold"
    )
    assert "hold" not in ACTIONABLE_ACTIVITIES


def test_stock_has_actionable() -> None:
    hold_only = StockAggregate(
        stock_key="NAME:x",
        name="X",
        nse="",
        bse="",
        sector="",
        direction="hold",
        score=0.0,
        median_share_change_pct=None,
        breadth_active=0,
        median_weight_delta_pp=None,
        breadth_weight_up=0,
        new_entry_count=0,
        fund_count=1,
        funds=[
            _fund(share_change_pct=0.0, activity="hold", current_weight_pct=1.0)
        ],
    )
    assert not stock_has_actionable_fund_activity(hold_only)
    active = StockAggregate(
        stock_key="NAME:y",
        name="Y",
        nse="",
        bse="",
        sector="",
        direction="increase",
        score=1.0,
        median_share_change_pct=10.0,
        breadth_active=1,
        median_weight_delta_pp=None,
        breadth_weight_up=0,
        new_entry_count=0,
        fund_count=1,
        funds=[_fund(share_change_pct=10.0)],
    )
    assert stock_has_actionable_fund_activity(active)
