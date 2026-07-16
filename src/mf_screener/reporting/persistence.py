"""Month-over-month persistence labels for HTML stock payloads."""

from __future__ import annotations

from typing import Any, Literal

ActivitySide = Literal["adding", "reducing", "mixed", "none"]
PersistenceStatus = Literal[
    "new_this_month",
    "still_adding",
    "still_reducing",
    "reversed",
    "continued_mixed",
    "unknown",
]


def activity_side(stock: dict[str, Any]) -> ActivitySide:
    adds = int(stock.get("addCount") or 0)
    reduces = int(stock.get("reduceCount") or 0)
    if adds > 0 and reduces > 0:
        return "mixed"
    if adds > 0:
        return "adding"
    if reduces > 0:
        return "reducing"
    return "none"


def _persistence_status(
    prior: ActivitySide | None,
    current: ActivitySide,
) -> PersistenceStatus:
    if prior is None:
        return "new_this_month"
    if prior == "none":
        return "new_this_month"
    if current == "adding" and prior in ("adding", "mixed"):
        return "still_adding"
    if current == "reducing" and prior in ("reducing", "mixed"):
        # prior mixed → reducing: treat as continued_mixed unless clean reduce→reduce
        if prior == "reducing":
            return "still_reducing"
        return "continued_mixed"
    if prior == "adding" and current == "reducing":
        return "reversed"
    if prior == "reducing" and current == "adding":
        return "reversed"
    if prior == "mixed" and current == "mixed":
        return "continued_mixed"
    if prior == "mixed" and current in ("adding", "reducing"):
        if current == "adding":
            return "still_adding"
        return "continued_mixed"
    if prior == "adding" and current == "mixed":
        return "continued_mixed"
    if prior == "reducing" and current == "mixed":
        return "continued_mixed"
    if current == "reducing" and prior == "reducing":
        return "still_reducing"
    return "continued_mixed"


def persistence_for_stock(
    current: dict[str, Any],
    *,
    prior: dict[str, Any] | None,
    prior_month_id: str | None,
) -> dict[str, Any]:
    if prior_month_id is None:
        return {
            "status": "unknown",
            "priorMonthId": "",
            "priorFundCount": 0,
            "priorAddCount": 0,
            "priorReduceCount": 0,
            "priorScore": 0.0,
        }
    if prior is None:
        return {
            "status": "new_this_month",
            "priorMonthId": prior_month_id,
            "priorFundCount": 0,
            "priorAddCount": 0,
            "priorReduceCount": 0,
            "priorScore": 0.0,
        }
    status = _persistence_status(activity_side(prior), activity_side(current))
    return {
        "status": status,
        "priorMonthId": prior_month_id,
        "priorFundCount": int(prior.get("fundCount") or 0),
        "priorAddCount": int(prior.get("addCount") or 0),
        "priorReduceCount": int(prior.get("reduceCount") or 0),
        "priorScore": float(prior.get("score") or 0),
    }


def attach_persistence_to_bundles(bundles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mutate each stock with persistence vs chronologically previous month.

    Bundles may be newest-first; we sort ascending by id for prior lookup,
    then preserve input order.
    """
    if not bundles:
        return bundles
    by_id = {str(b["id"]): b for b in bundles}
    chrono = sorted(by_id.keys())
    for i, month_id in enumerate(chrono):
        bundle = by_id[month_id]
        prior_id = chrono[i - 1] if i > 0 else None
        prior_map: dict[str, dict[str, Any]] = {}
        if prior_id:
            for s in by_id[prior_id].get("stocks") or []:
                key = str(s.get("stockKey") or "").strip()
                if key:
                    prior_map[key] = s
        for stock in bundle.get("stocks") or []:
            key = str(stock.get("stockKey") or "").strip()
            prior = prior_map.get(key) if prior_id else None
            stock["persistence"] = persistence_for_stock(
                stock,
                prior=prior,
                prior_month_id=prior_id,
            )
    return bundles
