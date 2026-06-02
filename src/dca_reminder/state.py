from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

from dca_reminder.rules import SignalResult, SignalType


EMPTY_STATE: dict = {"version": 2, "symbols": {}}


def load_state(path: str | Path) -> dict:
    state_path = Path(path)
    if not state_path.exists():
        return deepcopy(EMPTY_STATE)
    with state_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid state file: {state_path}")
    data.setdefault("version", 2)
    data.setdefault("symbols", {})
    return data


def save_state(path: str | Path, state: dict) -> bool:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    before = None
    if state_path.exists():
        before = state_path.read_text(encoding="utf-8")
    after = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if before == after:
        return False
    state_path.write_text(after, encoding="utf-8")
    return True


def get_symbol_state(state: dict, symbol: str) -> dict:
    symbols = state.setdefault("symbols", {})
    symbol_state = symbols.setdefault(symbol, {})
    symbol_state.setdefault("days", {})
    symbol_state.setdefault("months", {})
    symbol_state.setdefault("weeks", {})
    return symbol_state


def get_day_state(symbol_state: dict, day_key: str) -> dict:
    days = symbol_state.setdefault("days", {})
    day_state = days.setdefault(
        day_key,
        {
            "daily_trigger_prices": [],
            "intraday_signals": [],
            "daily_summary_sent": False,
        },
    )
    day_state.setdefault("daily_trigger_prices", [])
    day_state.setdefault("intraday_signals", [])
    day_state.setdefault("daily_summary_sent", False)
    return day_state


def get_month_state(symbol_state: dict, month_key: str, monthly_base_close: float) -> dict:
    months = symbol_state.setdefault("months", {})
    month_state = months.setdefault(
        month_key,
        {
            "monthly_base_close": monthly_base_close,
            "monthly_trigger_prices": [],
            "ma20_deviation_sent": False,
            "ma50_deviation_sent": False,
            "weekly_base_count": 0,
            "daily_drop_count": 0,
            "monthly_drop_count": 0,
            "monthly_summary_sent": False,
            "trigger_records": [],
        },
    )
    month_state.setdefault("monthly_base_close", monthly_base_close)
    month_state.setdefault("monthly_trigger_prices", [])
    month_state.setdefault("ma20_deviation_sent", False)
    month_state.setdefault("ma50_deviation_sent", False)
    month_state.setdefault("weekly_base_count", 0)
    month_state.setdefault("daily_drop_count", 0)
    month_state.setdefault("monthly_drop_count", 0)
    month_state.setdefault("monthly_summary_sent", False)
    month_state.setdefault("trigger_records", [])
    return month_state


def get_week_state(symbol_state: dict, week_key: str) -> dict:
    weeks = symbol_state.setdefault("weeks", {})
    week_state = weeks.setdefault(week_key, {"weekly_base_sent": False})
    week_state.setdefault("weekly_base_sent", False)
    return week_state


def apply_sent_signals(
    day_state: dict,
    month_state: dict,
    week_state: dict,
    signals: list[SignalResult],
    sent_at: str,
) -> None:
    for signal in signals:
        if signal.signal_type == SignalType.WEEKLY_BASE:
            week_state["weekly_base_sent"] = True
            month_state["weekly_base_count"] = int(month_state.get("weekly_base_count", 0)) + 1
        elif signal.signal_type == SignalType.DAILY_DROP:
            day_state.setdefault("daily_trigger_prices", []).append(float(signal.trigger_price))
            month_state["daily_drop_count"] = int(month_state.get("daily_drop_count", 0)) + 1
        elif signal.signal_type == SignalType.MONTHLY_DROP:
            month_state.setdefault("monthly_trigger_prices", []).append(float(signal.trigger_price))
            month_state["monthly_drop_count"] = int(month_state.get("monthly_drop_count", 0)) + 1
        elif signal.signal_type == SignalType.MA20_DEVIATION:
            month_state["ma20_deviation_sent"] = True
        elif signal.signal_type == SignalType.MA50_DEVIATION:
            month_state["ma50_deviation_sent"] = True

        record = {
            "signal_type": signal.signal_type.value,
            "sent_at": sent_at,
            "count": signal.count,
            "trigger_price": signal.trigger_price,
        }
        day_state.setdefault("intraday_signals", []).append(record)
        month_state.setdefault("trigger_records", []).append(record)


def count_day_signals(day_state: dict, signal_type: SignalType) -> int:
    return sum(1 for item in day_state.get("intraday_signals", []) if item.get("signal_type") == signal_type.value)
