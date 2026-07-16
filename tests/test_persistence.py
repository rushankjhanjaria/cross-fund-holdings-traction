from __future__ import annotations

from mf_screener.reporting.persistence import (
    activity_side,
    attach_persistence_to_bundles,
    persistence_for_stock,
)


def _stock(key: str, *, adds: int = 0, reduces: int = 0, score: float = 1.0, funds: int | None = None):
    return {
        "stockKey": key,
        "stockName": key,
        "score": score,
        "addCount": adds,
        "reduceCount": reduces,
        "holdCount": 0,
        "fundCount": funds if funds is not None else adds + reduces,
        "mixedSignal": adds > 0 and reduces > 0,
    }


def test_activity_side() -> None:
    assert activity_side(_stock("a", adds=2)) == "adding"
    assert activity_side(_stock("a", reduces=1)) == "reducing"
    assert activity_side(_stock("a", adds=1, reduces=1)) == "mixed"


def test_new_this_month() -> None:
    cur = _stock("NSE:A", adds=2, funds=2)
    p = persistence_for_stock(cur, prior=None, prior_month_id="2026-05")
    assert p["status"] == "new_this_month"


def test_still_adding() -> None:
    prior = _stock("NSE:A", adds=2, funds=2, score=10)
    cur = _stock("NSE:A", adds=3, funds=3, score=20)
    p = persistence_for_stock(cur, prior=prior, prior_month_id="2026-05")
    assert p["status"] == "still_adding"
    assert p["priorFundCount"] == 2


def test_reversed() -> None:
    prior = _stock("NSE:A", adds=2, funds=2)
    cur = _stock("NSE:A", reduces=2, funds=2)
    p = persistence_for_stock(cur, prior=prior, prior_month_id="2026-05")
    assert p["status"] == "reversed"


def test_attach_bundles() -> None:
    may = {
        "id": "2026-05",
        "stocks": [_stock("NSE:A", adds=2, funds=2), _stock("NSE:B", reduces=1, funds=1)],
    }
    june = {
        "id": "2026-06",
        "stocks": [
            _stock("NSE:A", adds=3, funds=3),
            _stock("NSE:B", adds=1, funds=1),
            _stock("NSE:C", adds=1, funds=1),
        ],
    }
    attach_persistence_to_bundles([june, may])
    by_key = {s["stockKey"]: s["persistence"]["status"] for s in june["stocks"]}
    assert by_key["NSE:A"] == "still_adding"
    assert by_key["NSE:B"] == "reversed"
    assert by_key["NSE:C"] == "new_this_month"
    assert may["stocks"][0]["persistence"]["status"] == "unknown"
