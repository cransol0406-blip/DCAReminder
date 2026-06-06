from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from dca_reminder.market_data import _previous_month_close, _trailing_30d_base_close


ET = ZoneInfo("America/New_York")


def test_previous_month_close_uses_split_adjusted_close_not_adj_close():
    index = pd.DatetimeIndex(
        [
            datetime(2026, 5, 29, tzinfo=ET),
            datetime(2026, 6, 1, tzinfo=ET),
        ]
    )
    daily = pd.DataFrame(
        {
            "Close": [100.0, 102.0],
            "Adj Close": [99.0, 101.0],
        },
        index=index,
    )
    close = _previous_month_close("SPY", daily, datetime(2026, 6, 2, tzinfo=ET))
    assert close == 100.0


def test_trailing_30d_base_close_uses_exact_trading_day_when_available():
    index = pd.DatetimeIndex(
        [
            datetime(2026, 5, 3, tzinfo=ET),
            datetime(2026, 5, 4, tzinfo=ET),
            datetime(2026, 6, 2, tzinfo=ET),
        ]
    )
    daily = pd.DataFrame({"Close": [98.0, 100.0, 120.0], "Adj Close": [90.0, 95.0, 119.0]}, index=index)
    close = _trailing_30d_base_close("SPY", daily, datetime(2026, 6, 3, tzinfo=ET))
    assert close == 100.0


def test_trailing_30d_base_close_searches_backward_from_non_trading_day():
    index = pd.DatetimeIndex(
        [
            datetime(2026, 5, 1, tzinfo=ET),
            datetime(2026, 5, 4, tzinfo=ET),
            datetime(2026, 6, 2, tzinfo=ET),
        ]
    )
    daily = pd.DataFrame({"Close": [97.0, 100.0, 120.0], "Adj Close": [91.0, 95.0, 119.0]}, index=index)
    close = _trailing_30d_base_close("SPY", daily, datetime(2026, 6, 2, tzinfo=ET))
    assert close == 97.0
