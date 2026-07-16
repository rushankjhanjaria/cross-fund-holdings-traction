from mf_screener.insights.evidence import build_evidence_pack
from mf_screener.insights.rules import rule_candidates
from mf_screener.insights.verify import verify_insights


def _stock(
    key: str,
    name: str,
    *,
    score: float = 10,
    fund_count: int = 3,
    add: int = 2,
    reduce: int = 0,
    new: int = 0,
    persist: str = "",
    prior_funds: int = 0,
    prior_score: float = 1.0,
    pct_vs_mid: str = "",
):
    return {
        "stockKey": key,
        "stockName": name,
        "nse": key.split(":")[-1] if ":" in key else "",
        "score": score,
        "fundCount": fund_count,
        "addCount": add,
        "reduceCount": reduce,
        "newCount": new,
        "holdCount": 0,
        "mixedSignal": add > 0 and reduce > 0,
        "adds": [{"fundName": "Fund A", "activity": "increase", "sharePctChange": "+10%", "pctAum": "1%"}],
        "reduces": (
            [{"fundName": "Fund B", "activity": "decrease", "sharePctChange": "-5%", "pctAum": "1%"}]
            if reduce
            else []
        ),
        "holds": [],
        "persistence": {
            "status": persist,
            "priorMonthId": "2026-05" if persist else "",
            "priorFundCount": prior_funds,
            "priorAddCount": 0,
            "priorReduceCount": 0,
            "priorScore": prior_score,
        },
        "pctVsMid": pct_vs_mid,
        "pctVsSma": pct_vs_mid,
    }


def test_evidence_pack_top_traction_and_still_reducing() -> None:
    stocks = [
        _stock("NSE:A", "Alpha Ltd", score=80, fund_count=5, add=4, pct_vs_mid="1.0"),
        _stock(
            "NSE:R",
            "Reduce Ltd",
            score=40,
            fund_count=3,
            add=0,
            reduce=3,
            persist="still_reducing",
            prior_funds=4,
        ),
        _stock("NSE:THIN", "Thin Ltd", score=500, fund_count=1, add=1),
    ]
    pack = build_evidence_pack(stocks, month_id="2026-06")
    assert "NSE:A" in pack["allowedStockKeys"]
    assert "stillAdding" not in pack
    assert "topNew" not in pack
    assert pack["stillReducing"][0]["stockKey"] == "NSE:R"
    assert len(pack["topTraction"]) == 2
    assert pack["topTraction"][0]["stockKey"] == "NSE:A"
    assert pack["topTraction"][0]["rank"] == 1
    keys = {r["stockKey"] for r in pack["topTraction"]}
    assert "NSE:THIN" not in keys


def test_still_early_requires_price_and_excludes_thin() -> None:
    stocks = [
        _stock("NSE:EARLY", "Early Ltd", score=90, fund_count=4, add=3, pct_vs_mid="-1.5"),
        _stock("NSE:LATE", "Late Ltd", score=95, fund_count=4, add=3, pct_vs_mid="12.0"),
        _stock("NSE:NOPCT", "NoPct Ltd", score=100, fund_count=4, add=3, pct_vs_mid=""),
        _stock("NSE:THIN", "Thin Ltd", score=200, fund_count=1, add=1, pct_vs_mid="0"),
    ]
    pack = build_evidence_pack(stocks, month_id="2026-06")
    cands = rule_candidates(pack)
    types = {c["type"] for c in cands}
    assert "still_early" in types
    early_keys = {c["stockKeys"][0] for c in cands if c["type"] == "still_early"}
    assert early_keys == {"NSE:EARLY"}


def test_exit_pressure_and_debate() -> None:
    stocks = [
        _stock(
            "NSE:EXIT",
            "Exit Ltd",
            score=50,
            fund_count=4,
            add=0,
            reduce=3,
            persist="still_reducing",
            prior_funds=5,
        ),
        _stock(
            "NSE:MIX",
            "Mix Ltd",
            score=60,
            fund_count=5,
            add=3,
            reduce=2,
        ),
        _stock(
            "NSE:FLIP",
            "Flip Ltd",
            score=40,
            fund_count=2,
            add=0,
            reduce=1,
            persist="reversed",
            prior_funds=4,
        ),
    ]
    pack = build_evidence_pack(stocks, month_id="2026-06")
    cands = rule_candidates(pack)
    by_type = {c["type"]: c for c in cands}
    assert "exit_pressure" in by_type
    assert by_type["exit_pressure"]["stockKeys"] == ["NSE:EXIT"]
    debate_keys = {c["stockKeys"][0] for c in cands if c["type"] == "debate"}
    assert "NSE:MIX" in debate_keys
    assert "NSE:FLIP" in debate_keys


def test_watchlist_echo_suppressed_without_delta() -> None:
    stocks = [
        _stock(
            "NSE:A",
            "Alpha Ltd",
            score=50,
            fund_count=4,
            add=3,
            prior_funds=4,
            prior_score=50,
            pct_vs_mid="0",
        ),
    ]
    pack = build_evidence_pack(
        stocks,
        month_id="2026-06",
        watchlist_items=[{"stockKey": "NSE:A", "name": "Alpha Ltd", "source": "auto"}],
    )
    # fundDelta=0, scoreDelta=0, status empty → no watchlist_delta
    cands = rule_candidates(pack)
    assert not any(c["type"] == "watchlist_delta" for c in cands)


def test_watchlist_delta_on_fund_change() -> None:
    stocks = [
        _stock(
            "NSE:A",
            "Alpha Ltd",
            score=50,
            fund_count=4,
            add=1,
            reduce=1,
            prior_funds=2,
            prior_score=40,
            pct_vs_mid="2",
        ),
    ]
    pack = build_evidence_pack(
        stocks,
        month_id="2026-06",
        watchlist_items=[{"stockKey": "NSE:A", "name": "Alpha Ltd", "source": "manual"}],
    )
    cands = rule_candidates(pack)
    wl = [c for c in cands if c["type"] == "watchlist_delta"]
    assert len(wl) == 1
    assert wl[0]["stockKeys"] == ["NSE:A"]


def test_verify_sets_section_and_rejects_bad() -> None:
    stocks = [
        _stock("NSE:EARLY", "Early Ltd", score=90, fund_count=4, add=3, pct_vs_mid="-1.0"),
    ]
    pack = build_evidence_pack(stocks, month_id="2026-06")
    cands = rule_candidates(pack)
    verified = verify_insights(cands, pack)
    assert verified
    assert all(v.get("section") in {"still_early", "exit_pressure", "debate", "watchlist_delta"} for v in verified)
    assert all("type" not in v for v in verified)

    bad = [
        {
            "id": "x",
            "type": "still_early",
            "headline": "Fake",
            "action": "research",
            "stockKeys": ["NSE:FAKE"],
            "body": "nope",
            "citations": [{"stockKey": "NSE:FAKE", "fields": {"fundCount": 4}}],
        },
        {
            "id": "y",
            "type": "still_adding_breadth",
            "headline": "Legacy",
            "action": "research",
            "stockKeys": ["NSE:EARLY"],
            "body": "nope",
            "citations": [
                {
                    "stockKey": "NSE:EARLY",
                    "fields": {"fundCount": 4, "addCount": 3, "reduceCount": 0},
                }
            ],
        },
    ]
    assert verify_insights(bad, pack) == []


def test_rules_only_end_to_end_dedupes() -> None:
    stocks = [
        _stock("NSE:EARLY", "Early Ltd", score=90, fund_count=5, add=4, pct_vs_mid="0"),
        _stock(
            "NSE:EXIT",
            "Exit Ltd",
            score=70,
            fund_count=3,
            add=0,
            reduce=3,
            persist="still_reducing",
            prior_funds=4,
        ),
        _stock("NSE:SPIKE", "Spike Ltd", fund_count=1, add=1, score=500),
    ]
    pack = build_evidence_pack(stocks, month_id="2026-06")
    cands = rule_candidates(pack)
    verified = verify_insights(cands, pack)
    keys = [v["stockKeys"][0] for v in verified]
    assert len(keys) == len(set(keys))
    assert "NSE:SPIKE" not in keys
    assert all(v["stockKeys"][0] in pack["allowedStockKeys"] for v in verified)
    assert pack["topTraction"][0]["stockKey"] == "NSE:EARLY"
