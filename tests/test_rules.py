from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dca_reminder.rules import MarketSnapshot, TriggerType, evaluate_triggers


ET = ZoneInfo("America/New_York")


def snapshot(
    current_price: float = 98.5,
    previous_close: float = 100.0,
    month_open: float = 105.0,
    ma20: float = 100.0,
    ma50: float = 100.0,
) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="SPY",
        timestamp=datetime(2026, 5, 29, 10, 0, tzinfo=ET),
        current_price=current_price,
        previous_close=previous_close,
        month_open=month_open,
        ma20=ma20,
        ma50=ma50,
    )


def trigger_values(triggers):
    return [trigger.trigger_type.value for trigger in triggers]


def test_daily_drop_triggers_at_boundary():
    triggers = evaluate_triggers(snapshot(current_price=98.5), set(), False)
    assert TriggerType.FIRST_DAILY_DROP.value in trigger_values(triggers)


def test_daily_drop_does_not_trigger_above_boundary():
    triggers = evaluate_triggers(snapshot(current_price=98.51), set(), False)
    assert TriggerType.FIRST_DAILY_DROP.value not in trigger_values(triggers)


def test_monthly_drop_triggers_at_boundary():
    triggers = evaluate_triggers(
        snapshot(current_price=95.0, previous_close=100.0, month_open=100.0),
        set(),
        False,
    )
    assert TriggerType.SECOND_MONTHLY_DROP.value in trigger_values(triggers)


def test_monthly_drop_does_not_trigger_above_boundary():
    triggers = evaluate_triggers(
        snapshot(current_price=95.01, previous_close=100.0, month_open=100.0),
        set(),
        False,
    )
    assert TriggerType.SECOND_MONTHLY_DROP.value not in trigger_values(triggers)


def test_ma_discount_requires_both_ma20_and_ma50():
    triggers = evaluate_triggers(
        snapshot(current_price=84.0, ma20=100.0, ma50=98.0),
        set(),
        False,
    )
    assert TriggerType.THIRD_MA_DISCOUNT.value not in trigger_values(triggers)

    triggers = evaluate_triggers(
        snapshot(current_price=84.0, ma20=100.0, ma50=100.0),
        set(),
        False,
    )
    assert TriggerType.THIRD_MA_DISCOUNT.value in trigger_values(triggers)


def test_sent_triggers_are_not_repeated():
    triggers = evaluate_triggers(
        snapshot(current_price=80.0, previous_close=100.0, month_open=100.0),
        {
            TriggerType.FIRST_DAILY_DROP.value,
            TriggerType.SECOND_MONTHLY_DROP.value,
            TriggerType.THIRD_MA_DISCOUNT.value,
        },
        False,
    )
    assert triggers == []


def test_month_end_fallback_only_when_first_trigger_not_sent():
    triggers = evaluate_triggers(snapshot(current_price=100.0), set(), True)
    assert TriggerType.MONTH_END_FALLBACK.value in trigger_values(triggers)

    triggers = evaluate_triggers(
        snapshot(current_price=100.0),
        {TriggerType.FIRST_DAILY_DROP.value},
        True,
    )
    assert TriggerType.MONTH_END_FALLBACK.value not in trigger_values(triggers)


def test_daily_drop_wins_over_month_end_fallback_for_first_trigger():
    triggers = evaluate_triggers(snapshot(current_price=98.5), set(), True)
    values = trigger_values(triggers)
    assert TriggerType.FIRST_DAILY_DROP.value in values
    assert TriggerType.MONTH_END_FALLBACK.value not in values
