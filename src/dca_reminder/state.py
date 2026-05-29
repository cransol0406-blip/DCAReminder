from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json


EMPTY_STATE: dict = {"symbols": {}}


def load_state(path: str | Path) -> dict:
    state_path = Path(path)
    if not state_path.exists():
        return deepcopy(EMPTY_STATE)
    with state_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid state file: {state_path}")
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


def get_symbol_month_state(state: dict, symbol: str, month_key: str) -> dict:
    symbols = state.setdefault("symbols", {})
    symbol_state = symbols.setdefault(symbol, {})
    months = symbol_state.setdefault("months", {})
    month_state = months.setdefault(
        month_key,
        {
            "first_trading_day_open": None,
            "sent_triggers": [],
            "sent_messages": [],
        },
    )
    month_state.setdefault("sent_triggers", [])
    month_state.setdefault("sent_messages", [])
    return month_state


def mark_trigger_sent(month_state: dict, trigger_type: str, sent_at: str) -> int:
    sent_triggers = month_state.setdefault("sent_triggers", [])
    if trigger_type not in sent_triggers:
        sent_triggers.append(trigger_type)
    sent_messages = month_state.setdefault("sent_messages", [])
    if not any(message.get("trigger_type") == trigger_type for message in sent_messages):
        sent_messages.append({"trigger_type": trigger_type, "sent_at": sent_at})
    return len(sent_triggers)
