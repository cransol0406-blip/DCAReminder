from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dca_reminder.rules import (
    STRATEGY_PARAMS,
    MarketSnapshot,
    SignalType,
    count_confirmed_drop_levels,
    evaluate_intraday_signals,
)


ET = ZoneInfo("America/New_York")


def snapshot(symbol: str = "SPY", price: float = 100.0) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        timestamp=datetime(2026, 6, 2, 10, 0, tzinfo=ET),
        price=price,
        previous_close=100.0,
        previous_month_close=100.0,
        trailing_30d_base_close=80.0,
        ma20=100.0,
        ma50=100.0,
    )


def signal_types(signals):
    return [signal.signal_type for signal in signals]


def test_spy_daily_drop_ladder_uses_1_5_percent_steps():
    params = STRATEGY_PARAMS["SPY"]
    day_state = {"daily_trigger_prices": []}
    month_state = {"monthly_base_close": 100.0}

    signals = evaluate_intraday_signals(snapshot("SPY", 98.50), params, day_state, month_state, {}, False)
    assert SignalType.DAILY_DROP in signal_types(signals)
    daily = next(signal for signal in signals if signal.signal_type == SignalType.DAILY_DROP)
    assert daily.count == 1
    assert round(daily.next_trigger_price, 2) == 97.02

    day_state = {"daily_trigger_prices": [98.50]}
    signals = evaluate_intraday_signals(snapshot("SPY", 97.02), params, day_state, month_state, {}, False)
    daily = next(signal for signal in signals if signal.signal_type == SignalType.DAILY_DROP)
    assert daily.count == 2
    assert round(daily.next_trigger_price, 2) == 95.57


def test_qqq_daily_drop_ladder_uses_2_percent_steps():
    params = STRATEGY_PARAMS["QQQ"]
    day_state = {"daily_trigger_prices": [98.00]}
    month_state = {"monthly_base_close": 100.0}

    signals = evaluate_intraday_signals(snapshot("QQQ", 96.04), params, day_state, month_state, {}, False)
    daily = next(signal for signal in signals if signal.signal_type == SignalType.DAILY_DROP)
    assert daily.count == 2
    assert round(daily.next_trigger_price, 2) == 94.12


def test_monthly_drop_ladder_uses_symbol_thresholds():
    spy = evaluate_intraday_signals(
        snapshot("SPY", 95.00),
        STRATEGY_PARAMS["SPY"],
        {},
        {"monthly_base_close": 100.0},
        {},
        False,
    )
    assert SignalType.MONTHLY_DROP in signal_types(spy)

    qqq = evaluate_intraday_signals(
        snapshot("QQQ", 93.00),
        STRATEGY_PARAMS["QQQ"],
        {},
        {"monthly_base_close": 100.0},
        {},
        False,
    )
    monthly = next(signal for signal in qqq if signal.signal_type == SignalType.MONTHLY_DROP)
    assert monthly.count == 1
    assert round(monthly.next_trigger_price, 2) == 86.49


def test_rebound_to_same_daily_ladder_does_not_repeat():
    params = STRATEGY_PARAMS["SPY"]
    signals = evaluate_intraday_signals(
        snapshot("SPY", 98.50),
        params,
        {"daily_trigger_prices": [98.50]},
        {"monthly_base_close": 100.0},
        {},
        False,
    )
    assert SignalType.DAILY_DROP not in signal_types(signals)


def test_ma20_and_ma50_are_independent_monthly_once_signals():
    params = STRATEGY_PARAMS["SPY"]
    signals = evaluate_intraday_signals(
        snapshot("SPY", 88.00),
        params,
        {},
        {"monthly_base_close": 100.0},
        {},
        False,
    )
    assert SignalType.MA20_DEVIATION in signal_types(signals)
    assert SignalType.MA50_DEVIATION in signal_types(signals)

    signals = evaluate_intraday_signals(
        snapshot("SPY", 80.00),
        params,
        {},
        {
            "monthly_base_close": 100.0,
            "ma20_deviation_sent": True,
            "ma50_deviation_sent": True,
        },
        {},
        False,
    )
    assert SignalType.MA20_DEVIATION not in signal_types(signals)
    assert SignalType.MA50_DEVIATION not in signal_types(signals)


def test_weekly_base_triggers_once_in_weekly_open_window():
    signals = evaluate_intraday_signals(
        snapshot("SPY", 101.0),
        STRATEGY_PARAMS["SPY"],
        {},
        {"monthly_base_close": 100.0},
        {"weekly_base_sent": False},
        True,
    )
    assert SignalType.WEEKLY_BASE in signal_types(signals)

    signals = evaluate_intraday_signals(
        snapshot("SPY", 101.0),
        STRATEGY_PARAMS["SPY"],
        {},
        {"monthly_base_close": 100.0},
        {"weekly_base_sent": True},
        True,
    )
    assert SignalType.WEEKLY_BASE not in signal_types(signals)


def test_multi_signal_order_uses_priority():
    signals = evaluate_intraday_signals(
        snapshot("SPY", 80.0),
        STRATEGY_PARAMS["SPY"],
        {},
        {"monthly_base_close": 100.0},
        {"weekly_base_sent": False},
        True,
    )
    assert signal_types(signals) == [
        SignalType.MA50_DEVIATION,
        SignalType.MA20_DEVIATION,
        SignalType.MONTHLY_DROP,
        SignalType.DAILY_DROP,
        SignalType.WEEKLY_BASE,
    ]


def test_confirmed_drop_level_count_uses_ideal_ladder():
    assert count_confirmed_drop_levels(95.57, 100.0, 0.015) == 3
    assert count_confirmed_drop_levels(94.12, 100.0, 0.02) == 3


def test_trailing_30d_change_uses_trailing_base_close():
    assert snapshot("SPY", 100.0).trailing_30d_change == 0.25
