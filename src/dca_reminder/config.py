from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    symbols: tuple[str, ...] = ("SPY", "QQQ")
    state_path: str = "data/state.json"
    dry_run: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


def load_config() -> Config:
    symbols_raw = os.getenv("SYMBOLS", "SPY,QQQ")
    symbols = tuple(symbol.strip().upper() for symbol in symbols_raw.split(",") if symbol.strip())
    return Config(
        symbols=symbols or ("SPY", "QQQ"),
        state_path=os.getenv("STATE_PATH", "data/state.json"),
        dry_run=os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"},
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )
