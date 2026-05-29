from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TriggerType(StrEnum):
    FIRST_DAILY_DROP = "first_daily_drop"
    MONTH_END_FALLBACK = "month_end_fallback"
    SECOND_MONTHLY_DROP = "second_monthly_drop"
    THIRD_MA_DISCOUNT = "third_ma_discount"


TRIGGER_LABELS = {
    TriggerType.FIRST_DAILY_DROP: "第一次定投：单日下跌超过1.5%",
    TriggerType.MONTH_END_FALLBACK: "第一次定投：本月未触发，最后交易日开盘前提醒",
    TriggerType.SECOND_MONTHLY_DROP: "第二次定投：单月跌幅超过5%",
    TriggerType.THIRD_MA_DISCOUNT: "第三次定投：价格低于MA20和MA50的15%及以上",
}


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timestamp: datetime
    current_price: float
    previous_close: float
    month_open: float
    ma20: float
    ma50: float

    @property
    def daily_drop(self) -> float:
        return self.current_price / self.previous_close - 1.0

    @property
    def monthly_drop(self) -> float:
        return self.current_price / self.month_open - 1.0


@dataclass(frozen=True)
class Trigger:
    trigger_type: TriggerType
    label: str
    snapshot: MarketSnapshot


def evaluate_triggers(
    snapshot: MarketSnapshot,
    sent_triggers: set[str],
    is_month_end_fallback_window: bool,
) -> list[Trigger]:
    triggers: list[Trigger] = []
    first_trigger_names = {
        TriggerType.FIRST_DAILY_DROP.value,
        TriggerType.MONTH_END_FALLBACK.value,
    }

    daily_first_triggered = (
        TriggerType.FIRST_DAILY_DROP.value not in sent_triggers
        and TriggerType.MONTH_END_FALLBACK.value not in sent_triggers
        and snapshot.daily_drop <= -0.015
    )
    if daily_first_triggered:
        triggers.append(_trigger(TriggerType.FIRST_DAILY_DROP, snapshot))

    if (
        not daily_first_triggered
        and is_month_end_fallback_window
        and sent_triggers.isdisjoint(first_trigger_names)
    ):
        triggers.append(_trigger(TriggerType.MONTH_END_FALLBACK, snapshot))

    if (
        TriggerType.SECOND_MONTHLY_DROP.value not in sent_triggers
        and snapshot.monthly_drop <= -0.05
    ):
        triggers.append(_trigger(TriggerType.SECOND_MONTHLY_DROP, snapshot))

    if (
        TriggerType.THIRD_MA_DISCOUNT.value not in sent_triggers
        and snapshot.current_price <= snapshot.ma20 * 0.85
        and snapshot.current_price <= snapshot.ma50 * 0.85
    ):
        triggers.append(_trigger(TriggerType.THIRD_MA_DISCOUNT, snapshot))

    return triggers


def _trigger(trigger_type: TriggerType, snapshot: MarketSnapshot) -> Trigger:
    return Trigger(trigger_type=trigger_type, label=TRIGGER_LABELS[trigger_type], snapshot=snapshot)
