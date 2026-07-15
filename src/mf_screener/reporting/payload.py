"""HTML report JSON payloads for stocks and months."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from mf_screener.aggregate import FundContribution, StockAggregate
from mf_screener.load import canonical_holding_display_name
from mf_screener.reporting.activity import (
    FundCsvActivity,
    append_activity_line,
    bucket_fund_contributions,
    is_mixed_signal,
)
from mf_screener.reporting.format import (
    direction_label_from_aggregate,
    entry_price_fields_camel,
    format_pct_of_aum,
    format_share_pct_change,
    stock_csv_direction,
)
from mf_screener.reporting.symbol_context import NameMapContext
from mf_screener.symbol_map import normalize_company_name


def fund_line(
    fund_name: str,
    activity: str,
    share_pct_change: str,
    pct_of_aum: str = "",
) -> dict[str, str]:
    return {
        "fundName": fund_name,
        "activity": activity,
        "sharePctChange": share_pct_change,
        "pctAum": pct_of_aum,
    }


def _fund_contribution_from_json(f: dict[str, Any]) -> FundContribution:
    return FundContribution(
        fund_slug=str(f.get("fund_slug") or ""),
        fund_display_name=str(f.get("fund_display_name") or ""),
        share_change_pct=f.get("share_change_pct"),
        share_change_abs=f.get("share_change_abs"),
        weight_delta_pp=f.get("weight_delta_pp"),
        current_weight_pct=float(f.get("current_weight_pct") or 0),
        is_new=bool(f.get("is_new")),
        activity=str(f.get("activity") or ""),
        history_url=str(f.get("history_url") or ""),
    )


def _line_from_fund(fund: FundContribution, activity: FundCsvActivity) -> dict[str, str]:
    return fund_line(
        fund.fund_display_name,
        activity,
        format_share_pct_change(fund),
        format_pct_of_aum(fund),
    )


def _stock_payload_core(
    *,
    stock_name: str,
    nse: str,
    stock_direction: str,
    score: float,
    adds: list[dict[str, str]],
    reduces: list[dict[str, str]],
    holds: list[dict[str, str]],
    price_fields: dict[str, str],
) -> dict[str, Any]:
    add_count = len(adds)
    reduce_count = len(reduces)
    hold_count = len(holds)
    fund_count = add_count + reduce_count + hold_count
    return {
        "stockName": stock_name,
        "nse": nse,
        "stockDirection": stock_direction,
        "score": round(score, 4),
        "mixedSignal": is_mixed_signal(add_count, reduce_count, hold_count),
        "adds": adds,
        "reduces": reduces,
        "holds": holds,
        "addCount": add_count,
        "reduceCount": reduce_count,
        "holdCount": hold_count,
        "fundCount": fund_count,
        "newCount": sum(1 for a in adds if a["activity"] == "new"),
        **price_fields,
    }


def stock_payload_from_aggregate(
    stock: StockAggregate,
    entry_by_stock_key: dict[str, dict] | None,
    name_map: NameMapContext | None = None,
) -> dict[str, Any]:
    adds, reduces, holds = bucket_fund_contributions(stock.funds, _line_from_fund)

    est = (entry_by_stock_key or {}).get(stock.stock_key)
    ctx = name_map or NameMapContext.load()
    nse = ctx.resolve_ticker(
        name=stock.name,
        nse_from_row=stock.nse or stock.bse,
        entry_estimate=est,
    )
    return _stock_payload_core(
        stock_name=stock.name,
        nse=nse,
        stock_direction=stock_csv_direction(stock),
        score=stock.score,
        adds=adds,
        reduces=reduces,
        holds=holds,
        price_fields=entry_price_fields_camel(est if isinstance(est, dict) else None),
    )


def stock_payload_from_report_json(
    stock: dict[str, Any],
    name_map: NameMapContext | None = None,
) -> dict[str, Any]:
    funds = [_fund_contribution_from_json(raw) for raw in (stock.get("funds") or [])]
    adds, reduces, holds = bucket_fund_contributions(funds, _line_from_fund)

    est = stock.get("entry_estimate")
    ctx = name_map or NameMapContext.load()
    nse = ctx.resolve_ticker(
        name=str(stock.get("name") or ""),
        nse_from_row=str(stock.get("nse") or stock.get("bse") or ""),
        entry_estimate=est if isinstance(est, dict) else None,
    )

    return _stock_payload_core(
        stock_name=str(stock.get("name") or ""),
        nse=nse,
        stock_direction=direction_label_from_aggregate(str(stock.get("direction") or "")),
        score=float(stock.get("score") or 0),
        adds=adds,
        reduces=reduces,
        holds=holds,
        price_fields=entry_price_fields_camel(est if isinstance(est, dict) else None),
    )


def build_stock_payloads_from_aggregates(
    stocks: Iterable[StockAggregate],
    entry_by_stock_key: dict[str, dict] | None,
    name_map: NameMapContext | None = None,
) -> list[dict[str, Any]]:
    ctx = name_map or NameMapContext.load()
    return [
        stock_payload_from_aggregate(s, entry_by_stock_key, ctx) for s in stocks
    ]


def build_stock_payloads_from_report_json(
    stocks: list[dict[str, Any]],
    name_map: NameMapContext | None = None,
) -> list[dict[str, Any]]:
    ctx = name_map or NameMapContext.load()
    payloads: list[dict[str, Any]] = []
    for raw in stocks:
        payload = stock_payload_from_report_json(raw, ctx)
        if payload["addCount"] > 0 or payload["reduceCount"] > 0:
            payloads.append(payload)
    payloads.sort(key=lambda s: (-s["score"], s["stockName"].lower()))
    return payloads


def build_stock_payloads_from_csv_rows(
    rows: list[dict[str, str]],
    name_map: NameMapContext | None = None,
) -> list[dict[str, Any]]:
    ctx = name_map or NameMapContext.load()
    by_stock: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        name = (row.get("stock_name") or "").strip()
        if name:
            by_stock[normalize_company_name(name)].append(row)

    stocks: list[dict[str, Any]] = []
    for _norm_key, group in by_stock.items():
        stock_name = canonical_holding_display_name(
            [row.get("stock_name") or "" for row in group]
        )
        sample = group[0]
        adds: list[dict[str, str]] = []
        reduces: list[dict[str, str]] = []
        holds: list[dict[str, str]] = []
        buckets = (adds, reduces, holds)
        for row in group:
            activity = (row.get("activity") or "").strip().lower()
            fund = (row.get("fund_name") or "").strip()
            if not activity or not fund:
                continue
            line = fund_line(
                fund,
                activity,
                row.get("share_pct_change") or "",
                row.get("pct_of_aum") or "",
            )
            append_activity_line(buckets, activity, line)

        nse = ctx.resolve_ticker(
            name=stock_name,
            nse_from_row=(sample.get("nse") or "").strip(),
        )
        snake = {
            "month_high": sample.get("month_high") or "",
            "month_low": sample.get("month_low") or "",
            "estimated_entry_mid": sample.get("estimated_entry_mid") or "",
            "close_latest": sample.get("close_latest") or "",
            "pct_vs_entry_mid": sample.get("pct_vs_entry_mid") or "",
        }
        price_camel = {
            "monthHigh": snake["month_high"],
            "monthLow": snake["month_low"],
            "entryMid": snake["estimated_entry_mid"],
            "closeLatest": snake["close_latest"],
            "pctVsMid": snake["pct_vs_entry_mid"],
        }
        stocks.append(
            _stock_payload_core(
                stock_name=stock_name,
                nse=nse,
                stock_direction=sample.get("stock_direction") or "",
                score=0.0,
                adds=adds,
                reduces=reduces,
                holds=holds,
                price_fields=price_camel,
            )
        )

    stocks = [s for s in stocks if s["addCount"] > 0 or s["reduceCount"] > 0]
    stocks.sort(key=lambda s: (-s["score"], s["stockName"].lower()))
    return stocks
