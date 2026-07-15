"""Fetch month OHLC via yfinance for MF entry band estimates."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

PRICE_CHUNK_SIZE = 75
CACHE_DIR = Path(__file__).resolve().parents[2] / "output" / "cache"


@dataclass(frozen=True)
class PriceSnapshot:
    nse: str
    yahoo_symbol: str
    month: str
    month_high: float | None
    month_low: float | None
    estimated_entry_mid: float | None
    close_latest: float | None
    pct_vs_entry_mid: float | None
    as_of_date: str | None
    status: str


def _month_bounds(month: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    year, mm = month.split("-")
    y, m = int(year), int(mm)
    start = pd.Timestamp(date(y, m, 1))
    if m == 12:
        end = pd.Timestamp(date(y + 1, 1, 1))
    else:
        end = pd.Timestamp(date(y, m + 1, 1))
    return start, end


def _to_yahoo_symbol(code: str, *, exchange: str = "NSE") -> str:
    suffix = "BO" if exchange.upper() == "BSE" else "NS"
    return f"{code.upper()}.{suffix}"


def _hist_for_ticker(data: pd.DataFrame, ticker: str, single: bool) -> pd.DataFrame | None:
    if data is None or data.empty:
        return None
    if single:
        return data.dropna(how="all")
    try:
        if ticker in data.columns.get_level_values(0):
            return data[ticker].dropna(how="all")
    except (AttributeError, KeyError, TypeError):
        return None
    return None


def _snapshot_from_history(
    nse: str,
    month: str,
    hist: pd.DataFrame | None,
    *,
    exchange: str = "NSE",
) -> PriceSnapshot:
    yahoo = _to_yahoo_symbol(nse, exchange=exchange)
    if hist is None or hist.empty:
        return PriceSnapshot(
            nse=nse,
            yahoo_symbol=yahoo,
            month=month,
            month_high=None,
            month_low=None,
            estimated_entry_mid=None,
            close_latest=None,
            pct_vs_entry_mid=None,
            as_of_date=None,
            status="empty",
        )

    frame = hist.copy()
    if isinstance(frame.index, pd.DatetimeIndex) and frame.index.tz is not None:
        frame.index = frame.index.tz_localize(None)

    month_start, month_end = _month_bounds(month)
    in_month = frame.loc[(frame.index >= month_start) & (frame.index < month_end)]
    if in_month.empty:
        in_month = frame

    month_high = float(in_month["High"].max())
    month_low = float(in_month["Low"].min())
    mid = (month_high + month_low) / 2.0
    close_latest = float(frame["Close"].iloc[-1])
    as_of = frame.index[-1]
    as_of_str = as_of.strftime("%Y-%m-%d")

    pct: float | None = None
    if mid > 0:
        pct = round((close_latest - mid) / mid * 100.0, 4)

    return PriceSnapshot(
        nse=nse,
        yahoo_symbol=yahoo,
        month=month,
        month_high=month_high,
        month_low=month_low,
        estimated_entry_mid=mid,
        close_latest=close_latest,
        pct_vs_entry_mid=pct,
        as_of_date=as_of_str,
        status="ok",
    )


def _cache_path(month: str) -> Path:
    return CACHE_DIR / f"prices_{month}.json"


def load_cache(month: str) -> dict[str, dict]:
    path = _cache_path(month)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(month: str, data: dict[str, dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(month).write_text(json.dumps(data, indent=2), encoding="utf-8")


def fetch_prices(
    listings: list[tuple[str, str]],
    month: str,
    *,
    refresh: bool = False,
) -> dict[str, PriceSnapshot]:
    """Fetch prices for (code, exchange) pairs; result keyed by listing code."""
    import yfinance as yf

    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for code, exchange in listings:
        if not code:
            continue
        key = (code.upper(), exchange.upper())
        if key not in seen:
            seen.add(key)
            unique.append(key)
    unique.sort()
    if not unique:
        return {}

    cached_raw = {} if refresh else load_cache(month)
    results: dict[str, PriceSnapshot] = {}
    to_fetch: list[tuple[str, str]] = []

    for code, exchange in unique:
        cache_key = f"{code}:{exchange}"
        if cache_key in cached_raw and not refresh:
            snap = PriceSnapshot(**cached_raw[cache_key])
            results[code] = snap
        else:
            to_fetch.append((code, exchange))

    month_start, _ = _month_bounds(month)
    end_fetch = date.today() + timedelta(days=1)
    start_str = month_start.date().isoformat()
    end_str = end_fetch.isoformat()

    for i in range(0, len(to_fetch), PRICE_CHUNK_SIZE):
        chunk = to_fetch[i : i + PRICE_CHUNK_SIZE]
        tickers = [_to_yahoo_symbol(code, exchange=exchange) for code, exchange in chunk]
        single = len(chunk) == 1
        try:
            data = yf.download(
                tickers,
                start=start_str,
                end=end_str,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception:
            data = pd.DataFrame()

        for (code, exchange), ticker in zip(chunk, tickers):
            hist = _hist_for_ticker(data, ticker, single)
            results[code] = _snapshot_from_history(
                code, month, hist, exchange=exchange
            )
            cache_key = f"{code}:{exchange}"
            cached_raw[cache_key] = asdict(results[code])

        if i + PRICE_CHUNK_SIZE < len(to_fetch):
            time.sleep(1.0)

    save_cache(month, cached_raw)
    return results


def entry_estimate_dict(snap: PriceSnapshot | None, *, unmapped: bool = False) -> dict:
    if unmapped or snap is None:
        return {"status": "unmapped" if unmapped else "missing"}
    return {
        "nse": snap.nse,
        "yahoo_symbol": snap.yahoo_symbol,
        "month": snap.month,
        "month_high": snap.month_high,
        "month_low": snap.month_low,
        "estimated_entry_mid": snap.estimated_entry_mid,
        "close_latest": snap.close_latest,
        "pct_vs_entry_mid": snap.pct_vs_entry_mid,
        "as_of_date": snap.as_of_date,
        "status": snap.status,
    }
