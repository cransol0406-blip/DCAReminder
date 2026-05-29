from __future__ import annotations

import requests

from dca_reminder.rules import Trigger


def build_message(trigger: Trigger, trigger_count: int) -> str:
    snapshot = trigger.snapshot
    timestamp = snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")
    return "\n".join(
        [
            "DCA Reminder",
            f"标的：{snapshot.symbol}",
            f"触发类型：{trigger.label}",
            f"当前价：{snapshot.current_price:.2f}",
            f"昨收：{snapshot.previous_close:.2f}",
            f"月初首个交易日开盘：{snapshot.month_open:.2f}",
            f"MA20：{snapshot.ma20:.2f}",
            f"MA50：{snapshot.ma50:.2f}",
            f"日涨跌幅：{snapshot.daily_drop:.2%}",
            f"月涨跌幅：{snapshot.monthly_drop:.2%}",
            f"本月触发次数：{trigger_count}/3",
            f"时间戳：{timestamp}",
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
