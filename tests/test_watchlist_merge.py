from mf_screener.reporting.watchlist import (
    add_manual_item,
    merge_auto_watchlist,
    remove_item,
)


def test_merge_preserves_manual_and_dedupes() -> None:
    existing = {
        "version": 1,
        "items": [
            {
                "stockKey": "NSE:KEEP",
                "name": "Keep Ltd",
                "nse": "KEEP",
                "pinnedAt": "2026-05",
                "source": "manual",
            },
            {
                "stockKey": "NSE:OLD",
                "name": "Old Auto",
                "nse": "OLD",
                "pinnedAt": "2026-05",
                "source": "auto",
            },
        ],
    }
    stocks = [
        {
            "stockKey": "NSE:KEEP",
            "stockName": "Keep Ltd Updated",
            "nse": "KEEP",
            "score": 99,
            "addCount": 2,
            "mixedSignal": False,
        },
        {
            "stockKey": "NSE:NEW",
            "stockName": "New Co",
            "nse": "NEW",
            "score": 50,
            "addCount": 1,
            "mixedSignal": False,
        },
        {
            "stockKey": "NSE:MIX",
            "stockName": "Mix Co",
            "nse": "MIX",
            "score": 40,
            "addCount": 1,
            "mixedSignal": True,
        },
    ]
    merged = merge_auto_watchlist(existing, stocks=stocks, month_id="2026-06", top_n=20)
    by_key = {i["stockKey"]: i for i in merged["items"]}
    assert by_key["NSE:KEEP"]["source"] == "manual"
    assert by_key["NSE:KEEP"]["name"] == "Keep Ltd"
    assert by_key["NSE:NEW"]["source"] == "auto"
    assert by_key["NSE:MIX"]["source"] == "auto"
    assert "NSE:OLD" in by_key  # prior auto kept unless overwritten


def test_add_remove_manual() -> None:
    wl = {"version": 1, "items": []}
    wl = add_manual_item(wl, stock_key="NSE:X", name="X", nse="X", pinned_at="2026-06")
    assert len(wl["items"]) == 1
    assert wl["items"][0]["source"] == "manual"
    wl = remove_item(wl, "NSE:X")
    assert wl["items"] == []
