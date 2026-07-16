"""Verify insight objects against the evidence pack (anti-hallucination gate)."""

from __future__ import annotations

from typing import Any

from mf_screener.insights.rules import ACTIONS, INSIGHT_TYPES, MAX_NARRATIVE

MAX_INSIGHTS = MAX_NARRATIVE


def _num_equal(a: Any, b: Any) -> bool:
    try:
        if isinstance(a, str) or isinstance(b, str):
            return str(a) == str(b)
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _field_matches(stock: dict[str, Any], field: str, value: Any) -> bool:
    if field == "persistence.status":
        return str((stock.get("persistence") or {}).get("status") or "") == str(value)
    if field == "priorFundCount":
        return _num_equal((stock.get("persistence") or {}).get("priorFundCount"), value)
    if field.startswith("persistence."):
        sub = field.split(".", 1)[1]
        return _num_equal((stock.get("persistence") or {}).get(sub), value)
    return _num_equal(stock.get(field), value)


def verify_insights(
    insights: list[dict[str, Any]],
    pack: dict[str, Any],
    *,
    max_insights: int = MAX_INSIGHTS,
) -> list[dict[str, Any]]:
    allowed_keys = set(pack.get("allowedStockKeys") or [])
    by_key = pack.get("stocksByKey") or {}
    verified: list[dict[str, Any]] = []

    for raw in insights:
        if len(verified) >= max_insights:
            break
        if not isinstance(raw, dict):
            continue
        action = str(raw.get("action") or "").strip()
        if action not in ACTIONS:
            continue
        insight_type = str(raw.get("type") or "").strip()
        if insight_type not in INSIGHT_TYPES:
            continue
        stock_keys = [str(k) for k in (raw.get("stockKeys") or []) if str(k)]
        if not stock_keys or any(k not in allowed_keys for k in stock_keys):
            continue
        citations = raw.get("citations") or []
        if not citations:
            continue
        ok = True
        for cite in citations:
            if not isinstance(cite, dict):
                ok = False
                break
            sk = str(cite.get("stockKey") or "")
            if sk not in by_key:
                ok = False
                break
            stock = by_key[sk]
            fields = cite.get("fields") or {}
            if not isinstance(fields, dict) or not fields:
                ok = False
                break
            for field, value in fields.items():
                if not _field_matches(stock, str(field), value):
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        verified.append(
            {
                "id": str(raw.get("id") or f"ins_{len(verified) + 1:02d}"),
                "section": insight_type,
                "headline": str(raw.get("headline") or "").strip(),
                "action": action,
                "stockKeys": stock_keys,
                "body": str(raw.get("body") or "").strip(),
                "citations": citations,
            }
        )
    return verified
