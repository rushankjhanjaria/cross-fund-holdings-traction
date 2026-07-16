"""Deterministic evidence pack from HTML stock payloads / report JSON."""

from __future__ import annotations

from typing import Any

from mf_screener.insights.rules import (
    is_debate,
    is_exit_pressure,
    is_multi_fund,
    is_still_early,
    is_top_traction_row,
    is_watchlist_delta,
)

CAP = 15
DECISION_BOARD_CAP = 16
FUND_NAME_LIMIT = 5
TOP_TRACTION_N = 10


def _fund_names(stock: dict[str, Any], limit: int = FUND_NAME_LIMIT) -> list[str]:
    names: list[str] = []
    for bucket in ("adds", "reduces", "holds"):
        for line in stock.get(bucket) or []:
            name = str(line.get("fundName") or "").strip()
            if name and name not in names:
                names.append(name)
            if len(names) >= limit:
                return names
    return names


def _stock_snippet(stock: dict[str, Any]) -> dict[str, Any]:
    pers = stock.get("persistence") or {}
    fund_count = int(stock.get("fundCount") or 0)
    prior_fund = int(pers.get("priorFundCount") or 0)
    score = float(stock.get("score") or 0)
    prior_score = float(pers.get("priorScore") or 0)
    pct = stock.get("pctVsSma") or stock.get("pctVsMid") or ""
    return {
        "stockKey": str(stock.get("stockKey") or ""),
        "name": str(stock.get("stockName") or stock.get("name") or ""),
        "nse": str(stock.get("nse") or ""),
        "score": score,
        "fundCount": fund_count,
        "addCount": int(stock.get("addCount") or 0),
        "reduceCount": int(stock.get("reduceCount") or 0),
        "newCount": int(stock.get("newCount") or 0),
        "mixedSignal": bool(stock.get("mixedSignal")),
        "fundNames": _fund_names(stock, FUND_NAME_LIMIT),
        "fundDelta": fund_count - prior_fund,
        "scoreDelta": score - prior_score,
        "breadth": "multi" if fund_count >= 3 else "thin",
        "persistence": {
            "status": str(pers.get("status") or ""),
            "priorMonthId": str(pers.get("priorMonthId") or ""),
            "priorFundCount": prior_fund,
            "priorAddCount": int(pers.get("priorAddCount") or 0),
            "priorReduceCount": int(pers.get("priorReduceCount") or 0),
            "priorScore": prior_score,
        },
        "pctVsMid": pct,
        "pctVsSma": pct,
        "sma30": stock.get("sma30") or "",
        "closeLatest": stock.get("closeLatest") or "",
        "entryMid": stock.get("entryMid") or "",
    }


def _top(stocks: list[dict[str, Any]], pred, *, n: int = CAP) -> list[dict[str, Any]]:
    picked = [s for s in stocks if pred(s)]
    picked.sort(key=lambda s: (-float(s.get("score") or 0), str(s.get("stockName") or "")))
    return [_stock_snippet(s) for s in picked[:n]]


def _top_traction_rows(stocks: list[dict[str, Any]], *, n: int = TOP_TRACTION_N) -> list[dict[str, Any]]:
    snippets = [_stock_snippet(s) for s in stocks if str(s.get("stockKey") or "")]
    eligible = [s for s in snippets if is_top_traction_row(s)]
    eligible.sort(key=lambda s: (-float(s.get("score") or 0), str(s.get("name") or "")))
    rows: list[dict[str, Any]] = []
    for i, s in enumerate(eligible[:n], start=1):
        pers = s.get("persistence") or {}
        rows.append(
            {
                "rank": i,
                "stockKey": s["stockKey"],
                "name": s["name"],
                "score": float(s.get("score") or 0),
                "fundCount": int(s.get("fundCount") or 0),
                "fundDelta": int(s.get("fundDelta") or 0),
                "addCount": int(s.get("addCount") or 0),
                "reduceCount": int(s.get("reduceCount") or 0),
                "pctVsMid": s.get("pctVsMid") or "",
                "pctVsSma": s.get("pctVsSma") or "",
                "persistenceStatus": str(pers.get("status") or ""),
            }
        )
    return rows


def _decision_row(snippet: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """Compact closed-world row for the decision board (no invented fields)."""
    pers = snippet.get("persistence") or {}
    return {
        "stockKey": snippet["stockKey"],
        "name": snippet["name"],
        "reason": reason,
        "fundCount": int(snippet.get("fundCount") or 0),
        "fundDelta": int(snippet.get("fundDelta") or 0),
        "scoreDelta": float(snippet.get("scoreDelta") or 0),
        "addCount": int(snippet.get("addCount") or 0),
        "reduceCount": int(snippet.get("reduceCount") or 0),
        "newCount": int(snippet.get("newCount") or 0),
        "mixedSignal": bool(snippet.get("mixedSignal")),
        "breadth": str(snippet.get("breadth") or "thin"),
        "persistenceStatus": str(pers.get("status") or ""),
        "fundNames": list(snippet.get("fundNames") or [])[:FUND_NAME_LIMIT],
        "pctVsMid": snippet.get("pctVsMid") or "",
        "pctVsSma": snippet.get("pctVsSma") or "",
        "sma30": snippet.get("sma30") or "",
        "score": float(snippet.get("score") or 0),
    }


def _build_decision_board(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Compact rows prioritizing triage patterns (still early → exit → debate → watchlist)."""
    board: list[dict[str, Any]] = []
    seen: set[str] = set()

    def push(snippet: dict[str, Any] | None, reason: str) -> None:
        if not snippet or len(board) >= DECISION_BOARD_CAP:
            return
        key = str(snippet.get("stockKey") or "")
        if not key or key in seen:
            return
        seen.add(key)
        board.append(_decision_row(snippet, reason=reason))

    for s in pack.get("topAdds") or []:
        if is_still_early(s):
            push(s, "stillEarly")

    for s in pack.get("topReduces") or []:
        if is_exit_pressure(s):
            push(s, "exitPressure")
    for s in pack.get("stillReducing") or []:
        if is_exit_pressure(s):
            push(s, "exitPressure")

    for s in pack.get("topMixed") or []:
        if is_debate(s):
            push(s, "debate")
    for s in pack.get("reversed") or []:
        if is_debate(s):
            push(s, "debate")

    for item in pack.get("watchlist") or []:
        snap = item.get("snapshot")
        if snap and is_watchlist_delta(snap):
            push(snap, "watchlistDelta")

    if len(board) < 12:
        for s in pack.get("topAdds") or []:
            if is_multi_fund(s):
                push(s, "topAddMulti")
            if len(board) >= 12:
                break

    return board[:DECISION_BOARD_CAP]


def build_evidence_pack(
    stocks: list[dict[str, Any]],
    *,
    month_id: str,
    watchlist_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build closed-world evidence for rules + LLM narration."""
    snippets = [_stock_snippet(s) for s in stocks if str(s.get("stockKey") or "")]
    by_key = {s["stockKey"]: s for s in snippets}

    pack: dict[str, Any] = {
        "monthId": month_id,
        "stocksByKey": by_key,
        "topAdds": _top(
            stocks,
            lambda s: int(s.get("addCount") or 0) > 0 and int(s.get("reduceCount") or 0) == 0,
        ),
        "topReduces": _top(
            stocks,
            lambda s: int(s.get("reduceCount") or 0) > 0 and int(s.get("addCount") or 0) == 0,
        ),
        "topMixed": _top(stocks, lambda s: bool(s.get("mixedSignal"))),
        "stillReducing": _top(
            stocks,
            lambda s: (s.get("persistence") or {}).get("status") == "still_reducing",
        ),
        "reversed": _top(
            stocks,
            lambda s: (s.get("persistence") or {}).get("status") == "reversed",
        ),
        "topTraction": _top_traction_rows(stocks),
        "watchlist": [],
        "allowedStockKeys": sorted(by_key.keys()),
        "allowedNames": sorted({s["name"] for s in snippets if s["name"]}),
        "allowedFundNames": sorted({n for s in snippets for n in s["fundNames"]}),
    }

    wl_out = []
    for item in watchlist_items or []:
        key = str(item.get("stockKey") or "").strip()
        if not key:
            continue
        snap = by_key.get(key)
        wl_out.append(
            {
                "stockKey": key,
                "name": str(item.get("name") or (snap or {}).get("name") or ""),
                "nse": str(item.get("nse") or (snap or {}).get("nse") or ""),
                "source": str(item.get("source") or ""),
                "snapshot": snap,
            }
        )
    pack["watchlist"] = wl_out
    pack["decisionBoard"] = _build_decision_board(pack)
    return pack
