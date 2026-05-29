from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal


ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


@dataclass(frozen=True)
class MarketWindow:
    is_trading_day: bool
    is_regular_window: bool
    is_month_end_fallback_window: bool
    month_key: str


def get_market_window(now: datetime | None = None) -> MarketWindow:
    now_et = (now or datetime.now(ET)).astimezone(ET)
    month_key = now_et.strftime("%Y-%m")
    nyse = mcal.get_calendar("NYSE")
    today = now_et.date()

    today_schedule = nyse.schedule(start_date=today.isoformat(), end_date=today.isoformat())
    if today_schedule.empty:
        return MarketWindow(False, False, False, month_key)

    row = today_schedule.iloc[0]
    market_open = _to_et(row["market_open"])
    market_close = _to_et(row["market_close"])
    is_regular = market_open <= now_et <= market_close

    month_start = today.replace(day=1)
    next_month = (pd.Timestamp(month_start) + pd.offsets.MonthBegin(1)).date()
    month_end = next_month - pd.Timedelta(days=1)
    month_schedule = nyse.schedule(start_date=month_start.isoformat(), end_date=month_end.isoformat())
    last_trading_day = month_schedule.index[-1].date()
    is_fallback = today == last_trading_day and (
        time(9, 0) <= now_et.time() < time(9, 30)
        or is_regular
    )

    return MarketWindow(True, is_regular, is_fallback, month_key)


def _to_et(value: pd.Timestamp) -> datetime:
    if value.tzinfo is None:
        value = value.tz_localize(UTC)
    return value.to_pydatetime().astimezone(ET)
