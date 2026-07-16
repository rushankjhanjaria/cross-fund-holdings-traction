"""Deterministic insight candidates from an evidence pack (monthly triage)."""

from __future__ import annotations

from typing import Any

ACTIONS = frozenset({"research", "monitor", "caution"})

INSIGHT_TYPES = frozenset(
    {"still_early", "exit_pressure", "debate", "watchlist_delta"}
)

MAX_NARRATIVE = 8

TYPE_CAPS: dict[str, int] = {
    "still_early": 3,
    "exit_pressure": 3,
    "debate": 2,
    "watchlist_delta": 2,
}


def parse_price_pct(stock: dict[str, Any]) -> float | None:
    """Parse pct vs SMA/mid; None if missing or unparseable."""
    raw = stock.get("pctVsSma") or stock.get("pctVsMid")
    if raw in ("", None):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def price_pct_field(stock: dict[str, Any]) -> tuple[str, str] | None:
    """Return (field_name, raw_string) for citation when a price pct exists."""
    for field in ("pctVsSma", "pctVsMid"):
        raw = stock.get(field)
        if raw not in ("", None):
            try:
                float(raw)
            except (TypeError, ValueError):
                continue
            return field, str(raw)
    return None


def is_multi_fund(stock: dict[str, Any]) -> bool:
    fc = int(stock.get("fundCount") or 0)
    add = int(stock.get("addCount") or 0)
    return fc >= 3 or (fc >= 2 and add >= 2)


def is_still_early(stock: dict[str, Any]) -> bool:
    if not is_multi_fund(stock):
        return False
    if int(stock.get("addCount") or 0) < 1:
        return False
    if int(stock.get("reduceCount") or 0) != 0:
        return False
    pct = parse_price_pct(stock)
    return pct is not None and pct <= 5


def is_exit_pressure(stock: dict[str, Any]) -> bool:
    fc = int(stock.get("fundCount") or 0)
    add = int(stock.get("addCount") or 0)
    reduce = int(stock.get("reduceCount") or 0)
    if add == 0 and reduce >= 2 and fc >= 2:
        return True
    status = str((stock.get("persistence") or {}).get("status") or "")
    return status == "still_reducing" and fc >= 2


def is_debate_mixed(stock: dict[str, Any]) -> bool:
    return int(stock.get("addCount") or 0) >= 2 and int(stock.get("reduceCount") or 0) >= 1


def is_debate_reversed(stock: dict[str, Any]) -> bool:
    pers = stock.get("persistence") or {}
    return (
        str(pers.get("status") or "") == "reversed"
        and int(pers.get("priorFundCount") or 0) >= 3
    )


def is_debate(stock: dict[str, Any]) -> bool:
    return is_debate_mixed(stock) or is_debate_reversed(stock)


def is_watchlist_delta(snap: dict[str, Any]) -> bool:
    """Meaningful change on a watchlisted snapshot (not a no-op echo)."""
    fund_delta = int(snap.get("fundDelta") or 0)
    score_delta = float(snap.get("scoreDelta") or 0)
    status = str((snap.get("persistence") or {}).get("status") or "")
    if fund_delta != 0:
        return True
    if status in ("reversed", "still_reducing"):
        return True
    if score_delta <= -20:
        return True
    return False


def is_top_traction_row(stock: dict[str, Any]) -> bool:
    fc = int(stock.get("fundCount") or 0)
    activity = (
        int(stock.get("addCount") or 0)
        + int(stock.get("reduceCount") or 0)
        + int(stock.get("newCount") or 0)
    )
    return fc >= 2 and activity > 0


def _cite(stock: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    return {"stockKey": stock["stockKey"], "fields": fields}


def _funds_clause(stock: dict[str, Any], *, limit: int = 2) -> str:
    names = [n for n in (stock.get("fundNames") or []) if n][:limit]
    if not names:
        return ""
    return f"; funds include {', '.join(names)}"


def _prior_fund(stock: dict[str, Any]) -> int:
    return int((stock.get("persistence") or {}).get("priorFundCount") or 0)


def rule_candidates(pack: dict[str, Any], *, max_insights: int = MAX_NARRATIVE) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = 0
    type_counts: dict[str, int] = {}
    used_keys: set[str] = set()

    def push(candidate: dict[str, Any], *, type_cap: int | None = None) -> None:
        nonlocal n
        if n >= max_insights:
            return
        key = str((candidate.get("stockKeys") or [""])[0] or "")
        if not key or key in used_keys:
            return
        t = str(candidate.get("type") or "")
        if t not in INSIGHT_TYPES:
            return
        cap = type_cap if type_cap is not None else TYPE_CAPS.get(t)
        if cap is not None and type_counts.get(t, 0) >= cap:
            return
        n += 1
        type_counts[t] = type_counts.get(t, 0) + 1
        used_keys.add(key)
        candidate["id"] = f"ins_{n:02d}"
        out.append(candidate)

    # still_early
    early_pool = list(pack.get("topAdds") or [])
    early_pool.sort(key=lambda s: (-float(s.get("score") or 0), str(s.get("name") or "")))
    for s in early_pool:
        if not is_still_early(s):
            continue
        prior = _prior_fund(s)
        cur = int(s.get("fundCount") or 0)
        pct_cite = price_pct_field(s)
        fields: dict[str, Any] = {
            "fundCount": cur,
            "addCount": int(s.get("addCount") or 0),
            "reduceCount": 0,
        }
        pct_note = ""
        if pct_cite:
            field, raw = pct_cite
            fields[field] = raw
            pct_note = f", {field}={raw}"
        push(
            {
                "headline": f"Still early: {s['name']}",
                "action": "research",
                "stockKeys": [s["stockKey"]],
                "body": (
                    f"{s['name']} shows multi-fund adds while price is still near the 30d SMA "
                    f"(funds {prior}→{cur}{pct_note}{_funds_clause(s)}). "
                    "Next: open the stock card and compare add breadth vs how far price already moved."
                ),
                "citations": [_cite(s, fields)],
                "type": "still_early",
            }
        )

    # exit_pressure
    exit_pool: list[dict[str, Any]] = []
    seen_exit: set[str] = set()
    for bucket in ("topReduces", "stillReducing"):
        for s in pack.get(bucket) or []:
            key = str(s.get("stockKey") or "")
            if not key or key in seen_exit:
                continue
            if is_exit_pressure(s):
                seen_exit.add(key)
                exit_pool.append(s)
    exit_pool.sort(key=lambda s: (-float(s.get("score") or 0), str(s.get("name") or "")))
    for s in exit_pool:
        prior = _prior_fund(s)
        cur = int(s.get("fundCount") or 0)
        reduces = int(s.get("reduceCount") or 0)
        status = str((s.get("persistence") or {}).get("status") or "")
        fields = {
            "fundCount": cur,
            "addCount": int(s.get("addCount") or 0),
            "reduceCount": reduces,
        }
        if status == "still_reducing":
            fields["persistence.status"] = "still_reducing"
            fields["priorFundCount"] = prior
        push(
            {
                "headline": f"Exit pressure: {s['name']}",
                "action": "caution",
                "stockKeys": [s["stockKey"]],
                "body": (
                    f"{s['name']} shows multi-fund selling "
                    f"(reduceCount={reduces}, funds {prior}→{cur}{_funds_clause(s)}). "
                    "Next: open reduce fund lines and decide whether this challenges a held long."
                ),
                "citations": [_cite(s, fields)],
                "type": "exit_pressure",
            }
        )

    # debate
    debate_pool: list[dict[str, Any]] = []
    seen_debate: set[str] = set()
    for bucket in ("topMixed", "reversed"):
        for s in pack.get(bucket) or []:
            key = str(s.get("stockKey") or "")
            if not key or key in seen_debate:
                continue
            if is_debate(s):
                seen_debate.add(key)
                debate_pool.append(s)
    debate_pool.sort(key=lambda s: (-float(s.get("score") or 0), str(s.get("name") or "")))
    for s in debate_pool:
        adds = int(s.get("addCount") or 0)
        reduces = int(s.get("reduceCount") or 0)
        cur = int(s.get("fundCount") or 0)
        prior = _prior_fund(s)
        fields = {"fundCount": cur, "addCount": adds, "reduceCount": reduces}
        if is_debate_reversed(s):
            fields["persistence.status"] = "reversed"
            fields["priorFundCount"] = prior
            why = f"reversed vs prior, funds {prior}→{cur}"
        else:
            why = f"addCount={adds}, reduceCount={reduces}, fundCount={cur}"
        push(
            {
                "headline": f"Debate: {s['name']}",
                "action": "caution",
                "stockKeys": [s["stockKey"]],
                "body": (
                    f"{s['name']} shows fund disagreement ({why}{_funds_clause(s)}). "
                    "Next: open add and reduce fund cards and note which AMCs disagree."
                ),
                "citations": [_cite(s, fields)],
                "type": "debate",
            }
        )

    # watchlist_delta
    for item in pack.get("watchlist") or []:
        snap = item.get("snapshot")
        if not snap or not is_watchlist_delta(snap):
            continue
        pers = snap.get("persistence") or {}
        status = str(pers.get("status") or "")
        prior = int(pers.get("priorFundCount") or 0)
        cur = int(snap.get("fundCount") or 0)
        fund_delta = int(snap.get("fundDelta") or 0)
        score_delta = float(snap.get("scoreDelta") or 0)
        name = snap.get("name") or item.get("name") or "Watchlist name"
        action = "caution" if status in ("reversed", "still_reducing") else "monitor"
        fields = {
            "fundCount": cur,
            "fundDelta": fund_delta,
            "scoreDelta": score_delta,
        }
        if status:
            fields["persistence.status"] = status
            fields["priorFundCount"] = prior
        push(
            {
                "headline": f"Watchlist: {name}",
                "action": action,
                "stockKeys": [snap["stockKey"]],
                "body": (
                    f"Watchlisted {name} changed "
                    f"(funds {prior}→{cur}, fundDelta={fund_delta}, scoreDelta={score_delta:.1f}"
                    f"{_funds_clause(snap)}). "
                    "Next: open the pinned card and re-check direction before next month."
                ),
                "citations": [_cite(snap, fields)],
                "type": "watchlist_delta",
            }
        )

    return out[:max_insights]
