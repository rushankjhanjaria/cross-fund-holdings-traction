#!/usr/bin/env python3
"""Top-100 traction backtest: month-end Close buy → latest close.

Buy price = last trading-day Close of the report month (actionable as-of
disclosure). SMA is shown in the traction UI for context, not used as the
backtest entry.

Usage:
  PYTHONPATH=src python3 scripts/top100_backtest.py --report output/may_traction.json
"""

from __future__ import annotations

import argparse
import json
import math
import pickle
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = REPO / "output" / "cache" / "yf_backtest"


def _month_id_from_report(report: dict[str, Any], report_path: Path) -> str:
    from mf_screener.report_month import MONTH_NAME_TO_NUM, month_id_from_report

    month = month_id_from_report(report, fallback_path=report_path)
    if month:
        return month
    # folder name fallback: …/funds/may → year from CSV suffix if present
    folder = str(report.get("folder") or report_path.parent)
    name = Path(folder).name.lower()
    mm = MONTH_NAME_TO_NUM.get(name)
    if not mm:
        raise ValueError(f"Cannot infer price_month from {report_path}")
    year = datetime.now(timezone.utc).year
    fund_dir = Path(folder)
    if fund_dir.is_dir():
        for p in fund_dir.glob("*.csv"):
            parts = p.stem.split("_")
            if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 2:
                year = 2000 + int(parts[-1])
                break
    return f"{year:04d}-{mm}"


def _month_bounds(month: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    from mf_screener.report_month import month_bounds as calendar_bounds

    start, end = calendar_bounds(month)
    return pd.Timestamp(start), pd.Timestamp(end)

def _symbol_fields(stock: dict[str, Any]) -> tuple[str, str | None]:
    """Return (nse_or_bse_code, yahoo_symbol)."""
    ee = stock.get("entry_estimate") or {}
    nse = (stock.get("nse") or ee.get("nse") or "").strip().upper()
    bse = (stock.get("bse") or "").strip().upper()
    yahoo = ee.get("yahoo_symbol")
    if yahoo:
        yahoo_s = str(yahoo)
        if not nse and yahoo_s.endswith(".NS"):
            nse = yahoo_s[:-3]
        elif not nse and yahoo_s.endswith(".BO"):
            nse = yahoo_s[:-3]
        return nse, yahoo_s
    if nse:
        return nse, f"{nse}.NS"
    if bse:
        return bse, f"{bse}.BO"
    return "", None


def _load_hist(cache_dir: Path, yahoo: str, *, refresh: bool) -> pd.DataFrame | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{yahoo}.pkl"
    if path.exists() and not refresh:
        try:
            hist = pickle.loads(path.read_bytes())
            if isinstance(hist, pd.DataFrame) and not hist.empty:
                return hist
        except Exception:
            pass

    import yfinance as yf

    try:
        hist = yf.Ticker(yahoo).history(period="1y", auto_adjust=True)
    except Exception:
        return None
    if hist is None or hist.empty:
        # empty marker
        path.write_bytes(pickle.dumps(pd.DataFrame()))
        return None
    path.write_bytes(pickle.dumps(hist))
    time.sleep(0.05)
    return hist


def _buy_from_hist(hist: pd.DataFrame, month: str) -> tuple[float | None, dict[str, Any]]:
    frame = hist.copy()
    if isinstance(frame.index, pd.DatetimeIndex) and frame.index.tz is not None:
        frame.index = frame.index.tz_localize(None)

    month_start, month_end = _month_bounds(month)
    through_month = frame.loc[frame.index < month_end]
    in_month = through_month.loc[through_month.index >= month_start]
    month_closes = in_month["Close"].dropna()
    month_n = int(len(month_closes))

    meta: dict[str, Any] = {
        "month_closes_count": month_n,
        "thin_history": False,
        "buy_method": None,
        "error": None,
    }

    if through_month.empty or "Close" not in through_month.columns:
        meta["buy_method"] = "no_data"
        meta["error"] = "no_data"
        meta["thin_history"] = True
        return None, meta

    if month_closes.empty:
        meta["buy_method"] = "no_month_closes"
        meta["error"] = "no_month_closes"
        meta["thin_history"] = True
        return None, meta

    # Actionable buy: last trading-day Close of the report month
    buy = float(month_closes.iloc[-1])
    meta["buy_method"] = f"month_end_close_{month.replace('-', '_')}"
    meta["thin_history"] = month_n < 10
    return buy, meta


def _current_close(hist: pd.DataFrame) -> float | None:
    frame = hist.copy()
    if isinstance(frame.index, pd.DatetimeIndex) and frame.index.tz is not None:
        frame.index = frame.index.tz_localize(None)
    closes = frame["Close"].dropna()
    if closes.empty:
        return None
    return float(closes.iloc[-1])


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def _bucket_returns(rows: list[dict[str, Any]]) -> dict[str, float]:
    priced = [r for r in rows if r.get("return_pct") is not None]
    priced.sort(key=lambda r: r["rank"])
    out: dict[str, float] = {}
    for label, lo, hi in (("1-25", 0, 25), ("26-50", 25, 50), ("51-75", 50, 75), ("76-100", 75, 100)):
        chunk = priced[lo:hi]
        if chunk:
            out[label] = round(statistics.mean(r["return_pct"] for r in chunk), 4)
    return out


def _distribution(returns: list[float]) -> dict[str, int]:
    buckets = {"<-20%": 0, "-20..-10%": 0, "-10..0%": 0, "0..10%": 0, "10..20%": 0, ">20%": 0}
    for r in returns:
        if r < -20:
            buckets["<-20%"] += 1
        elif r < -10:
            buckets["-20..-10%"] += 1
        elif r < 0:
            buckets["-10..0%"] += 1
        elif r < 10:
            buckets["0..10%"] += 1
        elif r < 20:
            buckets["10..20%"] += 1
        else:
            buckets[">20%"] += 1
    return buckets


def run_backtest(
    report_path: Path,
    *,
    top_n: int = 100,
    cache_dir: Path = DEFAULT_CACHE,
    refresh: bool = False,
    out_path: Path | None = None,
    summary_path: Path | None = None,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    month = _month_id_from_report(report, report_path)
    stocks = list(report.get("stocks") or [])
    stocks.sort(key=lambda s: (-float(s.get("score") or 0), s.get("name") or ""))
    universe = stocks[:top_n]

    rows: list[dict[str, Any]] = []
    for i, s in enumerate(universe, start=1):
        nse_code, yahoo = _symbol_fields(s)
        ee = s.get("entry_estimate") or {}
        row: dict[str, Any] = {
            "rank": i,
            "name": s.get("name"),
            "nse": nse_code,
            "score": round(float(s.get("score") or 0), 4),
            "yahoo_symbol": yahoo,
            "buy_price": None,
            "current_price": None,
            "return_pct": None,
            "thin_history": False,
            "month_closes_count": 0,
            "buy_method": None,
            "error": None,
            "estimated_entry_mid": ee.get("estimated_entry_mid"),
            "month_end_close": ee.get("month_end_close"),
            "sma_30": ee.get("sma_30"),
            "close_latest_heuristic": ee.get("close_latest"),
            "heuristic_return_pct": None,
            # feature dump for score tuning
            "breadth_active": s.get("breadth_active"),
            "breadth_weight_up": s.get("breadth_weight_up"),
            "median_share_change_pct": s.get("median_share_change_pct"),
            "median_weight_delta_pp": s.get("median_weight_delta_pp"),
            "new_entry_count": s.get("new_entry_count"),
            "fund_count": s.get("fund_count"),
            "direction": s.get("direction"),
        }
        buy_h = ee.get("month_end_close") or ee.get("estimated_entry_mid")
        close_h = ee.get("close_latest")
        if buy_h and close_h and float(buy_h) > 0:
            row["heuristic_return_pct"] = round(
                (float(close_h) - float(buy_h)) / float(buy_h) * 100.0, 4
            )

        if not yahoo:
            row["error"] = "no_symbol"
            rows.append(row)
            continue

        hist = _load_hist(cache_dir, yahoo, refresh=refresh)
        if hist is None or hist.empty:
            row["error"] = "no_data"
            row["thin_history"] = True
            row["buy_method"] = "no_data"
            rows.append(row)
            continue

        buy, meta = _buy_from_hist(hist, month)
        row.update(
            {
                "buy_price": None if buy is None else round(buy, 4),
                "thin_history": meta["thin_history"],
                "month_closes_count": meta["month_closes_count"],
                "buy_method": meta["buy_method"],
                "error": meta["error"],
            }
        )

        cur = _current_close(hist)
        row["current_price"] = None if cur is None else round(cur, 4)
        if buy and cur and buy > 0:
            row["return_pct"] = round((cur - buy) / buy * 100.0, 4)
        rows.append(row)

    priced = [r for r in rows if r.get("return_pct") is not None]
    returns = [float(r["return_pct"]) for r in priced]
    heuristic = [
        float(r["heuristic_return_pct"])
        for r in rows
        if r.get("heuristic_return_pct") is not None
    ]

    summary = {
        "top100_count": len(rows),
        "with_buy_and_current": len(priced),
        "without_prices": len(rows) - len(priced),
        "equal_weight_return_pct": round(statistics.mean(returns), 4) if returns else None,
        "median_return_pct": round(statistics.median(returns), 4) if returns else None,
        "win_rate_pct": round(100.0 * sum(1 for r in returns if r > 0) / len(returns), 2) if returns else None,
        "heuristic_equal_weight_return_pct": round(statistics.mean(heuristic), 4) if heuristic else None,
        "heuristic_median_return_pct": round(statistics.median(heuristic), 4) if heuristic else None,
        "heuristic_win_rate_pct": round(100.0 * sum(1 for r in heuristic if r > 0) / len(heuristic), 2)
        if heuristic
        else None,
        "heuristic_n": len(heuristic),
        "thin_history_count": sum(1 for r in rows if r.get("thin_history")),
        "distribution": _distribution(returns) if returns else {},
    }

    winners = sorted(priced, key=lambda r: -float(r["return_pct"]))[:10]
    losers = sorted(priced, key=lambda r: float(r["return_pct"]))[:10]
    score_vs = [
        {"name": r["name"], "nse": r["nse"], "score": r["score"], "return_pct": r["return_pct"]}
        for r in sorted(priced, key=lambda r: -float(r["score"]))
    ]
    corr = _pearson([float(r["score"]) for r in priced], returns)
    rank1 = next((r for r in rows if r["rank"] == 1), None)

    doc = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": str(report_path.resolve()),
        "universe": f"top_{top_n}_by_score",
        "buy_price_definition": (
            f"Last trading-day Close of "
            f"{datetime.strptime(month + '-01', '%Y-%m-%d').strftime('%B %Y')} "
            f"(month-end close; actionable as-of disclosure)"
        ),
        "current_price_definition": "latest available Close as of download date",
        "score_formula": (
            "composite = (breadth_active * breadth_bonus) + "
            "(breadth_active * log1p(median_share_change_pct) * share_weight) + "
            "(breadth_weight_up * median_weight_delta_pp * weight_scale) + "
            "(new_entry_count * new_boost) + (breadth_hold * hold_bonus) - "
            "(breadth_exit * exit_penalty); "
            "share_term only if median_share > 0 and breadth_active > 0; "
            "weight_term only if median_weight is not None and breadth_weight_up > 0; "
            "hold_term = funds with unchanged shares still held; "
            "defaults: breadth_bonus=5, share_weight=0.5, weight_scale=15, "
            "new_boost=5, hold_bonus=1, exit_penalty=20"
        ),
        "rank_mode": report.get("rank_mode") or "composite",
        "price_month": month,
        "summary": summary,
        "top_10_winners": [
            {
                "name": r["name"],
                "nse": r["nse"],
                "score": r["score"],
                "buy_price": r["buy_price"],
                "current_price": r["current_price"],
                "return_pct": r["return_pct"],
            }
            for r in winners
        ],
        "top_10_losers": [
            {
                "name": r["name"],
                "nse": r["nse"],
                "score": r["score"],
                "buy_price": r["buy_price"],
                "current_price": r["current_price"],
                "return_pct": r["return_pct"],
            }
            for r in losers
        ],
        "stocks": rows,
    }

    slim = {
        "summary": summary,
        "top_10_winners": doc["top_10_winners"],
        "top_10_losers": doc["top_10_losers"],
        "score_vs_return": score_vs,
        "pearson_corr_score_return": None if corr is None else round(corr, 6),
        "return_pct_rank1_by_score": None if not rank1 else rank1.get("return_pct"),
        "avg_return_by_rank_bucket": _bucket_returns(rows),
        "price_month": month,
    }

    slug = Path(str(report.get("folder") or report_path.stem)).name.lower()
    if slug.endswith("_traction"):
        slug = slug[: -len("_traction")]
    # Prefer month name from price_month
    month_names = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    mi = int(month.split("-")[1]) - 1
    slug = month_names[mi]

    out_path = out_path or (REPO / "output" / f"{slug}_top100_backtest.json")
    summary_path = summary_path or (REPO / "output" / f"{slug}_top100_backtest_summary.json")
    out_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(slim), encoding="utf-8")
    print(f"Wrote {out_path}", file=sys.stderr)
    print(f"Wrote {summary_path}", file=sys.stderr)
    print(json.dumps({"price_month": month, **summary, "pearson": slim["pearson_corr_score_return"]}, indent=2))
    return {"full": doc, "summary": slim, "out": str(out_path), "summary_out": str(summary_path)}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Top-100 traction month-end Close backtest")
    p.add_argument("--report", type=Path, required=True, help="*_traction.json path")
    p.add_argument("--top", type=int, default=100)
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--summary-out", type=Path, default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.report.is_file():
        print(f"Report not found: {args.report}", file=sys.stderr)
        return 1
    run_backtest(
        args.report,
        top_n=args.top,
        cache_dir=args.cache_dir,
        refresh=args.refresh,
        out_path=args.out,
        summary_path=args.summary_out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
