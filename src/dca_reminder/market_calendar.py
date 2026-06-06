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
    is_week_first_trading_day: bool
    is_week_last_trading_day: bool
    is_month_last_trading_day: bool
    is_weekly_open_reminder_window: bool
    is_close_summary_window: bool
    day_key: str
    week_key: str
    month_key: str


def get_market_window(now: datetime | None = None) -> MarketWindow:
    now_et = (now or datetime.now(ET)).astimezone(ET)
    today = now_et.date()
    day_key = today.isoformat()
    week_key = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
    month_key = now_et.strftime("%Y-%m")
    nyse = mcal.get_calendar("NYSE")

    today_schedule = nyse.schedule(start_date=day_key, end_date=day_key)
    if today_schedule.empty:
        return MarketWindow(False, False, False, False, False, False, False, day_key, week_key, month_key)

    row = today_schedule.iloc[0]
    market_open = _to_et(row["market_open"])
    market_close = _to_et(row["market_close"])
    is_regular = market_open <= now_et <= market_close

    week_start = today - pd.Timedelta(days=today.weekday())
    week_end = week_start + pd.Timedelta(days=6)
    week_schedule = nyse.schedule(start_date=week_start.isoformat(), end_date=week_end.isoformat())
    first_week_day = week_schedule.index[0].date()
    last_week_day = week_schedule.index[-1].date()
    is_week_first = today == first_week_day
    is_week_last = today == last_week_day

    month_start = today.replace(day=1)
    next_month = (pd.Timestamp(month_start) + pd.offsets.MonthBegin(1)).date()
    month_end = next_month - pd.Timedelta(days=1)
    month_schedule = nyse.schedule(start_date=month_start.isoformat(), end_date=month_end.isoformat())
    last_month_day = month_schedule.index[-1].date()
    is_month_last = today == last_month_day

    return MarketWindow(
        is_trading_day=True,
        is_regular_window=is_regular,
        is_week_first_trading_day=is_week_first,
        is_week_last_trading_day=is_week_last,
        is_month_last_trading_day=is_month_last,
        is_weekly_open_reminder_window=is_week_first and is_regular,
        is_close_summary_window=now_et.time() >= time(16, 15),
        day_key=day_key,
        week_key=week_key,
        month_key=month_key,
    )


def _to_et(value: pd.Timestamp) -> datetime:
    if value.tzinfo is None:
        value = value.tz_localize(UTC)
    return value.to_pydatetime().astimezone(ET)
