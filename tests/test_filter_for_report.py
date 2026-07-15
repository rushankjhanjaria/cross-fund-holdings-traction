from mf_screener.aggregate import FundContribution, StockAggregate
from mf_screener.reporting.filters import filter_for_report
from mf_screener.reporting.activity import stock_has_actionable_fund_activity


def _stock(
    key: str,
    funds: list[FundContribution],
    direction: str = "increase",
) -> StockAggregate:
    return StockAggregate(
        stock_key=key,
        name=key,
        nse="",
        bse="",
        sector="",
        direction=direction,  # type: ignore[arg-type]
        score=1.0,
        median_share_change_pct=1.0,
        breadth_active=1,
        median_weight_delta_pp=None,
        breadth_weight_up=0,
        new_entry_count=0,
        fund_count=len(funds),
        funds=funds,
    )


def _hold_fund() -> FundContribution:
    return FundContribution(
        fund_slug="h",
        fund_display_name="H",
        share_change_pct=0.0,
        share_change_abs=0.0,
        weight_delta_pp=None,
        current_weight_pct=1.0,
        is_new=False,
        activity="hold",
        history_url="",
    )


def _active_fund() -> FundContribution:
    return FundContribution(
        fund_slug="a",
        fund_display_name="A",
        share_change_pct=5.0,
        share_change_abs=50.0,
        weight_delta_pp=0.1,
        current_weight_pct=1.0,
        is_new=False,
        activity="active",
        history_url="",
    )


def test_excludes_hold_only() -> None:
    stocks = [_stock("hold", [_hold_fund()], direction="hold")]
    assert filter_for_report(stocks, include_holds=False) == []


def test_includes_mixed_activity() -> None:
    stocks = [_stock("mix", [_active_fund(), _hold_fund()])]
    out = filter_for_report(stocks, include_holds=False)
    assert len(out) == 1
    assert stock_has_actionable_fund_activity(out[0])
