from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dca_reminder.market_calendar import get_market_window


ET = ZoneInfo("America/New_York")


def test_first_trading_day_of_week_handles_holiday_monday():
    window = get_market_window(datetime(2026, 5, 26, 9, 30, tzinfo=ET))
    assert window.is_trading_day
    assert window.is_regular_window
    assert window.is_week_first_trading_day
    assert window.is_weekly_open_reminder_window


def test_non_first_trading_day_has_no_weekly_open_window():
    window = get_market_window(datetime(2026, 5, 27, 10, 0, tzinfo=ET))
    assert window.is_trading_day
    assert window.is_regular_window
    assert not window.is_week_first_trading_day
    assert not window.is_weekly_open_reminder_window


def test_close_summary_window_starts_at_1615_et():
    before = get_market_window(datetime(2026, 5, 29, 16, 14, tzinfo=ET))
    after = get_market_window(datetime(2026, 5, 29, 16, 15, tzinfo=ET))
    assert not before.is_close_summary_window
    assert after.is_close_summary_window


def test_month_last_trading_day_is_detected():
    window = get_market_window(datetime(2026, 5, 29, 16, 15, tzinfo=ET))
    assert window.is_month_last_trading_day


def test_weekend_is_not_trading_day():
    window = get_market_window(datetime(2026, 5, 30, 10, 0, tzinfo=ET))
    assert not window.is_trading_day
