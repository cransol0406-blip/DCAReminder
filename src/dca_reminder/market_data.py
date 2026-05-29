from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from dca_reminder.rules import MarketSnapshot


ET = ZoneInfo("America/New_York")


def fetch_snapshot(symbol: str, month_state: dict, now: datetime | None = None) -> MarketSnapshot:
    timestamp = (now or datetime.now(ET)).astimezone(ET)
    ticker = yf.Ticker(symbol)
    daily = ticker.history(period="6mo", interval="1d", auto_adjust=False, prepost=False)
    if daily.empty:
        raise RuntimeError(f"No daily market data returned for {symbol}")

    daily = _normalize_history(daily)
    completed_daily = daily[daily.index.date < timestamp.date()]
    if len(completed_daily) < 50:
        raise RuntimeError(f"Not enough completed daily bars for {symbol}")

    previous_close = float(completed_daily["Close"].iloc[-1])
    month_open = _month_open(symbol, daily, month_state, timestamp)
    ma20 = float(completed_daily["Close"].tail(20).mean())
    ma50 = float(completed_daily["Close"].tail(50).mean())
    current_price = _current_price(ticker, symbol)

    return MarketSnapshot(
        symbol=symbol,
        timestamp=timestamp,
        current_price=current_price,
        previous_close=previous_close,
        month_open=month_open,
        ma20=ma20,
        ma50=ma50,
    )


def _normalize_history(history: pd.DataFrame) -> pd.DataFrame:
    normalized = history.copy()
    if normalized.index.tz is None:
        normalized.index = normalized.index.tz_localize(ET)
    else:
        normalized.index = normalized.index.tz_convert(ET)
    return normalized.sort_index()


def _month_open(symbol: str, daily: pd.DataFrame, month_state: dict, timestamp: datetime) -> float:
    cached = month_state.get("first_trading_day_open")
    if cached is not None:
        return float(cached)

    month_mask = daily.index.strftime("%Y-%m") == timestamp.strftime("%Y-%m")
    month_daily = daily[month_mask]
    if month_daily.empty:
        raise RuntimeError(f"No current-month daily bars for {symbol}")
    month_open = float(month_daily["Open"].iloc[0])
    month_state["first_trading_day_open"] = month_open
    return month_open


def _current_price(ticker: yf.Ticker, symbol: str) -> float:
    intraday = ticker.history(period="1d", interval="5m", auto_adjust=False, prepost=False)
    if not intraday.empty and "Close" in intraday:
        close = intraday["Close"].dropna()
        if not close.empty:
            return float(close.iloc[-1])

    fast_info = getattr(ticker, "fast_info", {})
    for key in ("last_price", "regular_market_price", "previous_close"):
        try:
            value = fast_info.get(key) if hasattr(fast_info, "get") else fast_info[key]
        except Exception:
            continue
        if value is not None:
            return float(value)
    raise RuntimeError(f"No current price returned for {symbol}")
