from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dca_reminder.rules import MarketSnapshot, TriggerType, _trigger
from dca_reminder.state import get_symbol_month_state, mark_trigger_sent
from dca_reminder.telegram import build_message


def test_trigger_count_is_per_symbol_month():
    state = {"symbols": {}}
    spy_month = get_symbol_month_state(state, "SPY", "2026-05")
    qqq_month = get_symbol_month_state(state, "QQQ", "2026-05")

    assert mark_trigger_sent(spy_month, TriggerType.FIRST_DAILY_DROP.value, "2026-05-01T10:00:00") == 1
    assert mark_trigger_sent(spy_month, TriggerType.SECOND_MONTHLY_DROP.value, "2026-05-02T10:00:00") == 2
    assert mark_trigger_sent(qqq_month, TriggerType.FIRST_DAILY_DROP.value, "2026-05-01T10:00:00") == 1


def test_message_contains_updated_monthly_trigger_count():
    snapshot = MarketSnapshot(
        symbol="SPY",
        timestamp=datetime(2026, 5, 29, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        current_price=90.0,
        previous_close=100.0,
        month_open=100.0,
        ma20=110.0,
        ma50=110.0,
    )
    message = build_message(_trigger(TriggerType.SECOND_MONTHLY_DROP, snapshot), 2)
    assert "本月触发次数：2/3" in message
    assert "标的：SPY" in message
    assert "月跌幅：-10.00%" in message
