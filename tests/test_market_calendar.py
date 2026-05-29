from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dca_reminder.market_calendar import get_market_window


ET = ZoneInfo("America/New_York")


def test_month_end_fallback_window_starts_before_open():
    window = get_market_window(datetime(2026, 5, 29, 9, 15, tzinfo=ET))
    assert window.is_trading_day
    assert not window.is_regular_window
    assert window.is_month_end_fallback_window


def test_month_end_fallback_window_continues_during_regular_session():
    window = get_market_window(datetime(2026, 5, 29, 11, 15, tzinfo=ET))
    assert window.is_trading_day
    assert window.is_regular_window
    assert window.is_month_end_fallback_window


def test_month_end_fallback_window_includes_market_close():
    window = get_market_window(datetime(2026, 5, 29, 16, 0, tzinfo=ET))
    assert window.is_trading_day
    assert window.is_regular_window
    assert window.is_month_end_fallback_window


def test_month_end_fallback_window_excludes_after_close():
    window = get_market_window(datetime(2026, 5, 29, 16, 1, tzinfo=ET))
    assert window.is_trading_day
    assert not window.is_regular_window
    assert not window.is_month_end_fallback_window


def test_non_last_trading_day_has_no_fallback_window():
    window = get_market_window(datetime(2026, 5, 28, 11, 15, tzinfo=ET))
    assert window.is_trading_day
    assert window.is_regular_window
    assert not window.is_month_end_fallback_window
