from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dca_reminder.rules import STRATEGY_PARAMS, MarketSnapshot, SignalResult, SignalType
from dca_reminder.state import (
    apply_close_confirmations,
    apply_sent_signals,
    get_day_state,
    get_month_state,
    get_symbol_state,
    get_week_state,
)
from dca_reminder.telegram import (
    build_daily_summary_message,
    build_intraday_message,
    build_monthly_summary_message,
    build_weekly_summary_message,
)


ET = ZoneInfo("America/New_York")


def snapshot(price: float = 90.0) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="SPY",
        timestamp=datetime(2026, 6, 2, 10, 0, tzinfo=ET),
        price=price,
        previous_close=100.0,
        previous_month_close=100.0,
        trailing_30d_base_close=80.0,
        ma20=100.0,
        ma50=100.0,
    )


def test_state_records_are_independent_by_symbol_day_month_week():
    state = {"symbols": {}}
    spy = get_symbol_state(state, "SPY")
    qqq = get_symbol_state(state, "QQQ")
    spy_day = get_day_state(spy, "2026-06-02")
    spy_month = get_month_state(spy, "2026-06", 100.0)
    spy_week = get_week_state(spy, "2026-W23")
    qqq_month = get_month_state(qqq, "2026-06", 200.0)

    signal = SignalResult(SignalType.DAILY_DROP, 1, 98.5, 97.02, "daily")
    apply_sent_signals(spy_day, spy_month, spy_week, [signal], "2026-06-02T10:00:00-04:00")

    assert spy_month["daily_drop_count"] == 1
    assert spy_week["daily_drop_count"] == 1
    assert qqq_month["daily_drop_count"] == 0


def test_close_confirmations_update_aggregate_state_without_intraday_records():
    day_state = {
        "daily_trigger_prices": [],
        "intraday_signals": [],
        "close_confirmed_signals": [],
    }
    month_state = {
        "monthly_base_close": 100.0,
        "monthly_trigger_prices": [],
        "daily_drop_count": 0,
        "monthly_drop_count": 0,
        "ma20_deviation_sent": False,
        "ma50_deviation_sent": False,
        "trigger_records": [],
    }
    week_state = {
        "daily_drop_count": 0,
        "monthly_drop_count": 0,
        "ma20_deviation_sent": False,
        "ma50_deviation_sent": False,
        "trigger_records": [],
    }

    changed = apply_close_confirmations(
        day_state=day_state,
        month_state=month_state,
        week_state=week_state,
        confirmed_daily_count=1,
        confirmed_monthly_count=1,
        confirmed_ma20=True,
        confirmed_ma50=False,
        previous_close=100.0,
        previous_month_close=100.0,
        daily_drop_pct=0.015,
        monthly_drop_pct=0.05,
        confirmed_at="2026-06-02T16:15:00-04:00",
    )

    assert changed is True
    assert day_state["intraday_signals"] == []
    assert day_state["daily_trigger_prices"] == [98.5]
    assert month_state["monthly_trigger_prices"] == [95.0]
    assert week_state["daily_drop_count"] == 1
    assert month_state["daily_drop_count"] == 1
    assert week_state["monthly_drop_count"] == 1
    assert month_state["monthly_drop_count"] == 1
    assert week_state["ma20_deviation_sent"] is True
    assert month_state["ma20_deviation_sent"] is True
    assert day_state["close_confirmed_signals"][0]["source"] == "close_summary"


def test_intraday_message_lists_multiple_signals_without_trade_disclaimer():
    signals = [
        SignalResult(SignalType.MA50_DEVIATION, None, 90.0, None, "ma50"),
        SignalResult(SignalType.DAILY_DROP, 2, 90.0, 88.65, "daily"),
    ]
    message = build_intraday_message(snapshot(), STRATEGY_PARAMS["SPY"], signals)
    assert "【SPY 定投提醒｜盘中触发】" in message
    assert "美东时间：2026-06-02 10:00" in message
    assert "北京时间：2026-06-02 22:00" in message
    assert "当日：-10.00%（基准100.00）" in message
    assert "当月：-10.00%（基准100.00）" in message
    assert "30日：+12.50%（基准80.00）" in message
    assert "当日涨跌幅" not in message
    assert "近30日涨跌幅" not in message
    assert "50MA偏离提醒：是" in message
    assert "单日下跌提醒：第 2 次（-1.5%，-1.5%）" in message
    assert "阶梯阈值：" in message
    assert "单日本次触发价：90.00" in message
    assert "单日下一阶梯价：88.65" in message
    assert "单月本次触发价：未触发" in message
    assert "自动交易" not in message
    assert "不自动交易" not in message


def test_daily_summary_message_keeps_intraday_and_close_confirmation_separate():
    day_state = {
        "intraday_signals": [
            {"signal_type": SignalType.DAILY_DROP.value},
            {"signal_type": SignalType.MONTHLY_DROP.value},
        ]
    }
    message = build_daily_summary_message(
        snapshot(),
        STRATEGY_PARAMS["SPY"],
        day_state,
        confirmed_daily_count=0,
        confirmed_monthly_count=1,
        confirmed_ma20=False,
        confirmed_ma50=False,
        tomorrow_daily_trigger_price=88.65,
        next_monthly_trigger_price=85.50,
    )
    assert "盘中触发：" in message
    assert "美东时间：2026-06-02 10:00" in message
    assert "北京时间：2026-06-02 22:00" in message
    assert "30日：+12.50%（基准80.00）" in message
    assert "近30日涨跌幅" not in message
    assert "单日下跌提醒：1 次" in message
    assert "收盘确认：" in message
    assert "单日下跌提醒：无" in message
    assert "单月下跌提醒：1 次" in message


def test_weekly_summary_message_contains_weekly_counts_and_next_lines():
    week_state = {
        "weekly_base_count": 1,
        "daily_drop_count": 2,
        "monthly_drop_count": 1,
        "ma20_deviation_sent": False,
        "ma50_deviation_sent": True,
    }
    message = build_weekly_summary_message(
        snapshot(),
        STRATEGY_PARAMS["SPY"],
        "2026-W23",
        week_state,
        next_week_daily_trigger_price=88.65,
        next_monthly_trigger_price=85.50,
    )
    assert "【SPY 每周定投总结】" in message
    assert "周次：2026-W23" in message
    assert "本周收盘价：90.00" in message
    assert "当日：-10.00%（基准100.00）" in message
    assert "当月：-10.00%（基准100.00）" in message
    assert "30日：+12.50%（基准80.00）" in message
    assert "每周基础提醒：1 次" in message
    assert "单日下跌提醒：2 次" in message
    assert "50MA偏离提醒：是" in message
    assert "下周单日初始触发价：88.65" in message
    assert "本月月跌下一阶梯价：85.50" in message


def test_monthly_summary_message_contains_next_month_base():
    month_state = {
        "weekly_base_count": 4,
        "daily_drop_count": 2,
        "monthly_drop_count": 1,
        "ma20_deviation_sent": True,
        "ma50_deviation_sent": False,
    }
    message = build_monthly_summary_message(snapshot(), STRATEGY_PARAMS["SPY"], month_state)
    assert "【SPY 月度定投总结】" in message
    assert "美东时间：2026-06-02 10:00" in message
    assert "北京时间：2026-06-02 22:00" in message
    assert "当月：-10.00%（基准100.00）" in message
    assert "30日：+12.50%（基准80.00）" in message
    assert "本月涨跌幅" not in message
    assert "近30日涨跌幅" not in message
    assert "每周基础提醒：4 次" in message
    assert "下月月跌初始基准：90.00" in message
    assert "下月第一次月跌触发价：85.50" in message
