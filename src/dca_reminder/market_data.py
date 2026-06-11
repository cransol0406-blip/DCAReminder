from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from dca_reminder.rules import MarketSnapshot


ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class MarketData:
    symbol: str
    timestamp: datetime
    current_price: float
    previous_close: float
    previous_month_close: float
    trailing_30d_base_close: float
    intraday_ma20: float
    intraday_ma50: float
    close_price: float | None
    close_ma20: float | None
    close_ma50: float | None

    def intraday_snapshot(self) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=self.symbol,
            timestamp=self.timestamp,
            price=self.current_price,
            previous_close=self.previous_close,
            previous_month_close=self.previous_month_close,
            trailing_30d_base_close=self.trailing_30d_base_close,
            ma20=self.intraday_ma20,
            ma50=self.intraday_ma50,
        )

    def close_snapshot(self) -> MarketSnapshot | None:
        if not all(_is_valid_price(value) for value in (self.close_price, self.close_ma20, self.close_ma50)):
            return None
        return MarketSnapshot(
            symbol=self.symbol,
            timestamp=self.timestamp,
            price=self.close_price,
            previous_close=self.previous_close,
            previous_month_close=self.previous_month_close,
            trailing_30d_base_close=self.trailing_30d_base_close,
            ma20=self.close_ma20,
            ma50=self.close_ma50,
        )


def fetch_market_data(symbol: str, now: datetime | None = None, include_current_price: bool = True) -> MarketData:
    timestamp = (now or datetime.now(ET)).astimezone(ET)
    ticker = yf.Ticker(symbol)
    daily = ticker.history(
        period="1y",
        interval="1d",
        auto_adjust=False,
        actions=True,
        prepost=False,
    )
    if daily.empty:
        raise RuntimeError(f"No daily market data returned for {symbol}")

    daily = _normalize_history(daily)
    if "Adj Close" in daily.columns:
        daily = daily.drop(columns=["Adj Close"])

    completed_daily = daily[daily.index.date < timestamp.date()]
    if len(completed_daily) < 50:
        raise RuntimeError(f"Not enough completed daily bars for {symbol}")

    previous_close = float(completed_daily["Close"].iloc[-1])
    previous_month_close = _previous_month_close(symbol, daily, timestamp)
    trailing_30d_base_close = _trailing_30d_base_close(symbol, daily, timestamp)
    intraday_ma20 = float(completed_daily["Close"].tail(20).mean())
    intraday_ma50 = float(completed_daily["Close"].tail(50).mean())
    today_daily = daily[daily.index.date == timestamp.date()]
    close_price = None
    close_ma20 = None
    close_ma50 = None
    if not today_daily.empty:
        maybe_close_price = _to_valid_price(today_daily["Close"].iloc[-1])
        close_daily = daily[daily.index.date <= timestamp.date()]
        if maybe_close_price is not None and len(close_daily) >= 50:
            close_price = maybe_close_price
            close_ma20 = float(close_daily["Close"].tail(20).mean())
            close_ma50 = float(close_daily["Close"].tail(50).mean())
            if not _is_valid_price(close_ma20) or not _is_valid_price(close_ma50):
                close_price = None
                close_ma20 = None
                close_ma50 = None

    current_price = _current_price(ticker, symbol) if include_current_price else (close_price or previous_close)

    return MarketData(
        symbol=symbol,
        timestamp=timestamp,
        current_price=current_price,
        previous_close=previous_close,
        previous_month_close=previous_month_close,
        trailing_30d_base_close=trailing_30d_base_close,
        intraday_ma20=intraday_ma20,
        intraday_ma50=intraday_ma50,
        close_price=close_price,
        close_ma20=close_ma20,
        close_ma50=close_ma50,
    )


def _normalize_history(history: pd.DataFrame) -> pd.DataFrame:
    normalized = history.copy()
    if normalized.index.tz is None:
        normalized.index = normalized.index.tz_localize(ET)
    else:
        normalized.index = normalized.index.tz_convert(ET)
    return normalized.sort_index()


def _previous_month_close(symbol: str, daily: pd.DataFrame, timestamp: datetime) -> float:
    month_start = timestamp.date().replace(day=1)
    previous_month_daily = daily[daily.index.date < month_start]
    if previous_month_daily.empty:
        raise RuntimeError(f"No previous-month close available for {symbol}")
    return float(previous_month_daily["Close"].iloc[-1])


def _trailing_30d_base_close(symbol: str, daily: pd.DataFrame, timestamp: datetime) -> float:
    target_date = timestamp.date() - timedelta(days=30)
    trailing_daily = daily[daily.index.date <= target_date]
    if trailing_daily.empty:
        raise RuntimeError(f"No trailing 30-day base close available for {symbol}")
    return float(trailing_daily["Close"].iloc[-1])


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


def _to_valid_price(value) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if _is_valid_price(price) else None


def _is_valid_price(value) -> bool:
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
