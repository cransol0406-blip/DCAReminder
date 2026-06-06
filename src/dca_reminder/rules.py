from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SignalType(StrEnum):
    MA50_DEVIATION = "ma50_deviation"
    MA20_DEVIATION = "ma20_deviation"
    MONTHLY_DROP = "monthly_drop"
    DAILY_DROP = "daily_drop"
    WEEKLY_BASE = "weekly_base"


SIGNAL_PRIORITY = {
    SignalType.MA50_DEVIATION: 10,
    SignalType.MA20_DEVIATION: 20,
    SignalType.MONTHLY_DROP: 30,
    SignalType.DAILY_DROP: 40,
    SignalType.WEEKLY_BASE: 50,
}


SIGNAL_LABELS = {
    SignalType.MA50_DEVIATION: "50MA偏离提醒",
    SignalType.MA20_DEVIATION: "20MA偏离提醒",
    SignalType.MONTHLY_DROP: "单月下跌提醒",
    SignalType.DAILY_DROP: "单日下跌提醒",
    SignalType.WEEKLY_BASE: "每周基础定投提醒",
}


@dataclass(frozen=True)
class StrategyParams:
    symbol: str
    daily_drop_pct: float
    monthly_drop_pct: float
    ma20_deviation_pct: float
    ma50_deviation_pct: float

    @property
    def daily_factor(self) -> float:
        return 1.0 - self.daily_drop_pct

    @property
    def monthly_factor(self) -> float:
        return 1.0 - self.monthly_drop_pct

    @property
    def ma20_factor(self) -> float:
        return 1.0 - self.ma20_deviation_pct

    @property
    def ma50_factor(self) -> float:
        return 1.0 - self.ma50_deviation_pct


STRATEGY_PARAMS = {
    "SPY": StrategyParams("SPY", 0.015, 0.05, 0.08, 0.12),
    "QQQ": StrategyParams("QQQ", 0.02, 0.07, 0.12, 0.16),
}


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timestamp: datetime
    price: float
    previous_close: float
    previous_month_close: float
    trailing_30d_base_close: float
    ma20: float
    ma50: float

    @property
    def daily_change(self) -> float:
        return self.price / self.previous_close - 1.0

    @property
    def monthly_change(self) -> float:
        return self.price / self.previous_month_close - 1.0

    @property
    def trailing_30d_change(self) -> float:
        return self.price / self.trailing_30d_base_close - 1.0


@dataclass(frozen=True)
class SignalResult:
    signal_type: SignalType
    count: int | None
    trigger_price: float | None
    next_trigger_price: float | None
    description: str

    @property
    def label(self) -> str:
        return SIGNAL_LABELS[self.signal_type]


def evaluate_intraday_signals(
    snapshot: MarketSnapshot,
    params: StrategyParams,
    day_state: dict,
    month_state: dict,
    week_state: dict,
    is_weekly_open_reminder_window: bool,
) -> list[SignalResult]:
    signals: list[SignalResult] = []

    if is_weekly_open_reminder_window and not week_state.get("weekly_base_sent"):
        signals.append(
            SignalResult(
                signal_type=SignalType.WEEKLY_BASE,
                count=None,
                trigger_price=None,
                next_trigger_price=None,
                description="本周第一个实际交易日开盘提醒",
            )
        )

    daily_prices = _float_list(day_state.get("daily_trigger_prices", []))
    daily_base = daily_prices[-1] if daily_prices else snapshot.previous_close
    daily_trigger_line = daily_base * params.daily_factor
    if _at_or_below_price_line(snapshot.price, daily_trigger_line):
        count = len(daily_prices) + 1
        signals.append(
            SignalResult(
                signal_type=SignalType.DAILY_DROP,
                count=count,
                trigger_price=daily_trigger_line,
                next_trigger_price=daily_trigger_line * params.daily_factor,
                description=f"第 {count} 次；当前价低于单日阶梯线 {daily_trigger_line:.2f}",
            )
        )

    monthly_prices = _float_list(month_state.get("monthly_trigger_prices", []))
    monthly_base = monthly_prices[-1] if monthly_prices else float(month_state["monthly_base_close"])
    monthly_trigger_line = monthly_base * params.monthly_factor
    if _at_or_below_price_line(snapshot.price, monthly_trigger_line):
        count = len(monthly_prices) + 1
        signals.append(
            SignalResult(
                signal_type=SignalType.MONTHLY_DROP,
                count=count,
                trigger_price=monthly_trigger_line,
                next_trigger_price=monthly_trigger_line * params.monthly_factor,
                description=f"第 {count} 次；当前价低于月跌阶梯线 {monthly_trigger_line:.2f}",
            )
        )

    if not month_state.get("ma20_deviation_sent") and _at_or_below_price_line(snapshot.price, snapshot.ma20 * params.ma20_factor):
        signals.append(
            SignalResult(
                signal_type=SignalType.MA20_DEVIATION,
                count=None,
                trigger_price=snapshot.price,
                next_trigger_price=None,
                description=f"当前价低于MA20阈值 {snapshot.ma20 * params.ma20_factor:.2f}",
            )
        )

    if not month_state.get("ma50_deviation_sent") and _at_or_below_price_line(snapshot.price, snapshot.ma50 * params.ma50_factor):
        signals.append(
            SignalResult(
                signal_type=SignalType.MA50_DEVIATION,
                count=None,
                trigger_price=snapshot.price,
                next_trigger_price=None,
                description=f"当前价低于MA50阈值 {snapshot.ma50 * params.ma50_factor:.2f}",
            )
        )

    return sorted(signals, key=lambda signal: SIGNAL_PRIORITY[signal.signal_type])


def count_confirmed_drop_levels(price: float, initial_base: float, drop_pct: float) -> int:
    count = 0
    next_line = initial_base * (1.0 - drop_pct)
    while _at_or_below_price_line(price, next_line):
        count += 1
        next_line *= 1.0 - drop_pct
    return count


def next_daily_trigger_price(previous_close: float, params: StrategyParams) -> float:
    return previous_close * params.daily_factor


def next_monthly_trigger_price(month_state: dict, params: StrategyParams) -> float:
    monthly_prices = _float_list(month_state.get("monthly_trigger_prices", []))
    base = monthly_prices[-1] if monthly_prices else float(month_state["monthly_base_close"])
    return base * params.monthly_factor


def _float_list(values: list) -> list[float]:
    return [float(value) for value in values]


def _at_or_below_price_line(price: float, line: float) -> bool:
    return price <= round(line, 2) + 1e-9
