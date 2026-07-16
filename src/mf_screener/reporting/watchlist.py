"""Durable watchlist stored beside traction reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WATCHLIST_FILENAME = "watchlist.json"
AUTO_PIN_TOP_N = 20


def watchlist_path(reports_dir: Path) -> Path:
    return Path(reports_dir) / WATCHLIST_FILENAME


def empty_watchlist() -> dict[str, Any]:
    return {"version": 1, "items": []}


def load_watchlist(reports_dir: Path) -> dict[str, Any]:
    path = watchlist_path(reports_dir)
    if not path.is_file():
        return empty_watchlist()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return empty_watchlist()
    if not isinstance(data, dict):
        return empty_watchlist()
    items = data.get("items")
    if not isinstance(items, list):
        items = []
    return {"version": int(data.get("version") or 1), "items": items}


def save_watchlist(reports_dir: Path, watchlist: dict[str, Any]) -> Path:
    path = watchlist_path(reports_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": int(watchlist.get("version") or 1),
        "items": list(watchlist.get("items") or []),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _item_key(item: dict[str, Any]) -> str:
    return str(item.get("stockKey") or "").strip()


def merge_auto_watchlist(
    existing: dict[str, Any],
    *,
    stocks: list[dict[str, Any]],
    month_id: str,
    top_n: int = AUTO_PIN_TOP_N,
) -> dict[str, Any]:
    """Merge top adds/mixed stocks as auto pins; never wipe manual pins."""
    candidates = [
        s
        for s in stocks
        if int(s.get("addCount") or 0) > 0 or bool(s.get("mixedSignal"))
    ]
    candidates.sort(key=lambda s: (-float(s.get("score") or 0), str(s.get("stockName") or "")))
    auto_items = []
    for s in candidates[:top_n]:
        key = str(s.get("stockKey") or "").strip()
        if not key:
            continue
        auto_items.append(
            {
                "stockKey": key,
                "name": str(s.get("stockName") or ""),
                "nse": str(s.get("nse") or ""),
                "pinnedAt": month_id,
                "source": "auto",
            }
        )

    by_key: dict[str, dict[str, Any]] = {}
    for item in existing.get("items") or []:
        if not isinstance(item, dict):
            continue
        key = _item_key(item)
        if not key:
            continue
        by_key[key] = dict(item)

    for item in auto_items:
        key = item["stockKey"]
        prev = by_key.get(key)
        if prev and str(prev.get("source") or "") == "manual":
            continue
        by_key[key] = item

    items = sorted(by_key.values(), key=lambda x: str(x.get("name") or "").lower())
    return {"version": 1, "items": items}


def add_manual_item(
    watchlist: dict[str, Any],
    *,
    stock_key: str,
    name: str = "",
    nse: str = "",
    pinned_at: str = "",
) -> dict[str, Any]:
    key = (stock_key or "").strip()
    if not key:
        return watchlist
    items = [dict(i) for i in (watchlist.get("items") or []) if isinstance(i, dict)]
    items = [i for i in items if _item_key(i) != key]
    items.append(
        {
            "stockKey": key,
            "name": name,
            "nse": nse,
            "pinnedAt": pinned_at,
            "source": "manual",
        }
    )
    items.sort(key=lambda x: str(x.get("name") or "").lower())
    return {"version": 1, "items": items}


def remove_item(watchlist: dict[str, Any], stock_key: str) -> dict[str, Any]:
    key = (stock_key or "").strip()
    items = [
        dict(i)
        for i in (watchlist.get("items") or [])
        if isinstance(i, dict) and _item_key(i) != key
    ]
    return {"version": 1, "items": items}
