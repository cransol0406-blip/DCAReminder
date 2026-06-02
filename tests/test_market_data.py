from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from dca_reminder.market_data import _previous_month_close


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
