"""Fetch month OHLC via yfinance for MF entry band + month-end SMA estimates."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, fields
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PRICE_CHUNK_SIZE = 75
CACHE_DIR = Path(__file__).resolve().parents[2] / "output" / "cache"
SMA_WINDOW = 30
# Extra calendar days before month start so a 30d SMA as of month-end is possible
SMA_LOOKBACK_DAYS = 90


@dataclass(frozen=True)
class PriceSnapshot:
    nse: str
    yahoo_symbol: str
    month: str
    month_high: float | None
    month_low: float | None
    estimated_entry_mid: float | None
    month_end_close: float | None
    sma_30: float | None
    close_latest: float | None
    pct_vs_entry_mid: float | None
    pct_vs_sma: float | None
    as_of_date: str | None
    status: str


from mf_screener.report_month import month_bounds as _calendar_month_bounds


def _month_bounds(month: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start, end = _calendar_month_bounds(month)
    return pd.Timestamp(start), pd.Timestamp(end)


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


def _empty_snapshot(nse: str, month: str, *, exchange: str = "NSE", status: str = "empty") -> PriceSnapshot:
    return PriceSnapshot(
        nse=nse,
        yahoo_symbol=_to_yahoo_symbol(nse, exchange=exchange),
        month=month,
        month_high=None,
        month_low=None,
        estimated_entry_mid=None,
        month_end_close=None,
        sma_30=None,
        close_latest=None,
        pct_vs_entry_mid=None,
        pct_vs_sma=None,
        as_of_date=None,
        status=status,
    )


def _sma_asof_month_end(closes_through_month: pd.Series, *, window: int = SMA_WINDOW) -> float | None:
    closes = closes_through_month.dropna()
    if closes.empty:
        return None
    if len(closes) >= window:
        return float(closes.iloc[-window:].mean())
    if len(closes) >= 15:
        return float(closes.mean())
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
        return _empty_snapshot(nse, month, exchange=exchange, status="empty")

    frame = hist.copy()
    if isinstance(frame.index, pd.DatetimeIndex) and frame.index.tz is not None:
        frame.index = frame.index.tz_localize(None)

    month_start, month_end = _month_bounds(month)
    through_month = frame.loc[frame.index < month_end]
    in_month = through_month.loc[through_month.index >= month_start]
    if in_month.empty:
        in_month = through_month if not through_month.empty else frame

    month_high = float(in_month["High"].max()) if "High" in in_month.columns and not in_month.empty else None
    month_low = float(in_month["Low"].min()) if "Low" in in_month.columns and not in_month.empty else None
    mid = None
    if month_high is not None and month_low is not None:
        mid = (month_high + month_low) / 2.0

    month_closes = in_month["Close"].dropna() if "Close" in in_month.columns else pd.Series(dtype=float)
    month_end_close = float(month_closes.iloc[-1]) if not month_closes.empty else None

    closes_through = through_month["Close"].dropna() if "Close" in through_month.columns else pd.Series(dtype=float)
    sma_30 = _sma_asof_month_end(closes_through)

    close_latest = float(frame["Close"].dropna().iloc[-1]) if "Close" in frame.columns and not frame["Close"].dropna().empty else None
    as_of = frame.index[-1]
    as_of_str = as_of.strftime("%Y-%m-%d")

    pct_mid: float | None = None
    if mid is not None and mid > 0 and close_latest is not None:
        pct_mid = round((close_latest - mid) / mid * 100.0, 4)

    pct_sma: float | None = None
    if sma_30 is not None and sma_30 > 0 and close_latest is not None:
        pct_sma = round((close_latest - sma_30) / sma_30 * 100.0, 4)

    return PriceSnapshot(
        nse=nse,
        yahoo_symbol=yahoo,
        month=month,
        month_high=month_high,
        month_low=month_low,
        estimated_entry_mid=mid,
        month_end_close=month_end_close,
        sma_30=sma_30,
        close_latest=close_latest,
        pct_vs_entry_mid=pct_mid,
        pct_vs_sma=pct_sma,
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


def _snapshot_from_cache_dict(raw: dict) -> PriceSnapshot:
    """Load cache rows; fill new SMA fields if an older cache is present."""
    known = {f.name for f in fields(PriceSnapshot)}
    payload = {k: raw.get(k) for k in known if k in raw}
    for name in ("month_end_close", "sma_30", "pct_vs_sma"):
        payload.setdefault(name, None)
    return PriceSnapshot(**payload)  # type: ignore[arg-type]


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
            snap = _snapshot_from_cache_dict(cached_raw[cache_key])
            # Older caches lack SMA — refetch those symbols
            if snap.sma_30 is None and snap.status == "ok":
                to_fetch.append((code, exchange))
            else:
                results[code] = snap
        else:
            to_fetch.append((code, exchange))

    month_start, _ = _month_bounds(month)
    end_fetch = date.today() + timedelta(days=1)
    start_fetch = (month_start - pd.Timedelta(days=SMA_LOOKBACK_DAYS)).date()
    start_str = start_fetch.isoformat()
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
        "month_end_close": snap.month_end_close,
        "sma_30": snap.sma_30,
        "close_latest": snap.close_latest,
        "pct_vs_entry_mid": snap.pct_vs_entry_mid,
        "pct_vs_sma": snap.pct_vs_sma,
        "as_of_date": snap.as_of_date,
        "status": snap.status,
    }
