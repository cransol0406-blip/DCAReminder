from __future__ import annotations

from zoneinfo import ZoneInfo

import requests

from dca_reminder.rules import (
    MarketSnapshot,
    SignalResult,
    SignalType,
    StrategyParams,
)
from dca_reminder.state import count_day_signals


CN = ZoneInfo("Asia/Shanghai")


def build_intraday_message(
    snapshot: MarketSnapshot,
    params: StrategyParams,
    signals: list[SignalResult],
) -> str:
    signal_by_type = {signal.signal_type: signal for signal in signals}
    return "\n".join(
        [
            f"【{snapshot.symbol} 定投提醒｜盘中触发】",
            "",
            *_time_lines(snapshot),
            "",
            f"当前价格：{snapshot.price:.2f}",
            _change_line("当日涨跌幅", snapshot.daily_change, snapshot.previous_close),
            _change_line("当月涨跌幅", snapshot.monthly_change, snapshot.previous_month_close),
            _change_line("近30日涨跌幅", snapshot.trailing_30d_change, snapshot.trailing_30d_base_close),
            "",
            "触发条件：",
            f"- 单日下跌提醒：{_count_text(signal_by_type.get(SignalType.DAILY_DROP))}",
            f"- 单月下跌提醒：{_count_text(signal_by_type.get(SignalType.MONTHLY_DROP))}",
            f"- 20MA偏离提醒：{_yes_no(SignalType.MA20_DEVIATION in signal_by_type)}",
            f"- 50MA偏离提醒：{_yes_no(SignalType.MA50_DEVIATION in signal_by_type)}",
            f"- 每周基础定投提醒：{_yes_no(SignalType.WEEKLY_BASE in signal_by_type)}",
            "",
            "触发说明：",
            f"- 单日下跌阈值：较上一单日基准跌超 {params.daily_drop_pct:.1%}",
            f"- 单月下跌阈值：较上月月末收盘价或上一次月跌触发价跌超 {params.monthly_drop_pct:.1%}",
            f"- 20MA条件：低于20日均线超 {params.ma20_deviation_pct:.1%}",
            f"- 50MA条件：低于50日均线超 {params.ma50_deviation_pct:.1%}",
        ]
    )


def build_daily_summary_message(
    snapshot: MarketSnapshot,
    params: StrategyParams,
    day_state: dict,
    confirmed_daily_count: int,
    confirmed_monthly_count: int,
    confirmed_ma20: bool,
    confirmed_ma50: bool,
    tomorrow_daily_trigger_price: float,
    next_monthly_trigger_price: float,
) -> str:
    return "\n".join(
        [
            f"【{snapshot.symbol} 每日定投总结】",
            "",
            *_time_lines(snapshot),
            "",
            f"收盘价：{snapshot.price:.2f}",
            _change_line("当日涨跌幅", snapshot.daily_change, snapshot.previous_close),
            _change_line("当月涨跌幅", snapshot.monthly_change, snapshot.previous_month_close),
            _change_line("近30日涨跌幅", snapshot.trailing_30d_change, snapshot.trailing_30d_base_close),
            "",
            "盘中触发：",
            f"- 单日下跌提醒：{count_day_signals(day_state, SignalType.DAILY_DROP)} 次",
            f"- 单月下跌提醒：{count_day_signals(day_state, SignalType.MONTHLY_DROP)} 次",
            f"- 20MA偏离提醒：{_yes_no(count_day_signals(day_state, SignalType.MA20_DEVIATION) > 0)}",
            f"- 50MA偏离提醒：{_yes_no(count_day_signals(day_state, SignalType.MA50_DEVIATION) > 0)}",
            f"- 每周基础定投提醒：{_yes_no(count_day_signals(day_state, SignalType.WEEKLY_BASE) > 0)}",
            "",
            "收盘确认：",
            f"- 单日下跌提醒：{_count_or_none(confirmed_daily_count)}",
            f"- 单月下跌提醒：{_count_or_none(confirmed_monthly_count)}",
            f"- 20MA偏离提醒：{_yes_no(confirmed_ma20)}",
            f"- 50MA偏离提醒：{_yes_no(confirmed_ma50)}",
            "",
            "下一提醒线：",
            f"- 明日单日初始触发价：{tomorrow_daily_trigger_price:.2f}",
            f"- 本月月跌下一阶梯价：{next_monthly_trigger_price:.2f}",
            "",
            "备注：",
            "- 单日阶梯价仅当日有效，收盘后失效；",
            "- 明日单日初始触发价按今日收盘价重新计算；",
            "- 月跌阶梯价在本月内继续有效。",
        ]
    )


def build_monthly_summary_message(
    snapshot: MarketSnapshot,
    params: StrategyParams,
    month_state: dict,
) -> str:
    next_month_base = snapshot.price
    return "\n".join(
        [
            f"【{snapshot.symbol} 月度定投总结】",
            "",
            f"月份：{snapshot.timestamp.strftime('%Y-%m')}",
            *_time_lines(snapshot),
            "",
            f"月末收盘价：{snapshot.price:.2f}",
            _change_line("本月涨跌幅", snapshot.monthly_change, snapshot.previous_month_close),
            _change_line("近30日涨跌幅", snapshot.trailing_30d_change, snapshot.trailing_30d_base_close),
            "",
            "本月提醒统计：",
            f"- 每周基础提醒：{int(month_state.get('weekly_base_count', 0))} 次",
            f"- 单日下跌提醒：{int(month_state.get('daily_drop_count', 0))} 次",
            f"- 单月下跌提醒：{int(month_state.get('monthly_drop_count', 0))} 次",
            f"- 20MA偏离提醒：{_yes_no(bool(month_state.get('ma20_deviation_sent')))}",
            f"- 50MA偏离提醒：{_yes_no(bool(month_state.get('ma50_deviation_sent')))}",
            "",
            "下月基准：",
            f"- 下月月跌初始基准：{next_month_base:.2f}",
            f"- 下月第一次月跌触发价：{next_month_base * params.monthly_factor:.2f}",
            "",
            "备注：",
            "下月月跌初始基准 = 本月最后一个交易日收盘价。",
        ]
    )


def send_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": chat_id, "text": text},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed: {payload}")


def _count_text(signal: SignalResult | None) -> str:
    if signal is None:
        return "未触发"
    return f"第 {signal.count} 次"


def _count_or_none(count: int) -> str:
    return f"{count} 次" if count else "无"


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def _change_line(label: str, change: float, base_price: float) -> str:
    return f"{label}：{change:+.2%}（基准：{base_price:.2f}）"


def _time_lines(snapshot: MarketSnapshot) -> list[str]:
    market_time = snapshot.timestamp.strftime("%Y-%m-%d %H:%M")
    beijing_time = snapshot.timestamp.astimezone(CN).strftime("%Y-%m-%d %H:%M")
    return [
        f"美股时间：{market_time}",
        f"北京时间：{beijing_time}",
    ]
