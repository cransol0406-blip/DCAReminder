from __future__ import annotations

from datetime import datetime
import logging

from dca_reminder.config import load_config
from dca_reminder.market_calendar import ET, get_market_window
from dca_reminder.market_data import fetch_snapshot
from dca_reminder.rules import evaluate_triggers
from dca_reminder.state import get_symbol_month_state, load_state, mark_trigger_sent, save_state
from dca_reminder.telegram import build_message, send_message


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def main() -> int:
    config = load_config()
    now = datetime.now(ET)
    window = get_market_window(now)
    if not window.is_trading_day:
        LOGGER.info("Not a NYSE trading day; exiting.")
        return 0
    if not (window.is_regular_window or window.is_month_end_fallback_window):
        LOGGER.info("Outside monitoring windows; exiting.")
        return 0

    state = load_state(config.state_path)
    state_changed = False

    for symbol in config.symbols:
        month_state = get_symbol_month_state(state, symbol, window.month_key)
        try:
            snapshot = fetch_snapshot(symbol, month_state, now)
            state_changed = True
        except Exception as exc:
            LOGGER.warning("Skipping %s because market data failed: %s", symbol, exc)
            continue

        sent_triggers = set(month_state.get("sent_triggers", []))
        triggers = evaluate_triggers(snapshot, sent_triggers, window.is_month_end_fallback_window)
        if not triggers:
            LOGGER.info("%s has no new triggers.", symbol)
            continue

        for trigger in triggers:
            trigger_count = len(set(month_state.get("sent_triggers", []))) + 1
            message = build_message(trigger, trigger_count)
            if config.dry_run:
                LOGGER.info("DRY_RUN Telegram message:\n%s", message)
            else:
                if not config.telegram_bot_token or not config.telegram_chat_id:
                    raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
                send_message(config.telegram_bot_token, config.telegram_chat_id, message)
            actual_count = mark_trigger_sent(
                month_state,
                trigger.trigger_type.value,
                snapshot.timestamp.isoformat(),
            )
            LOGGER.info("%s sent trigger %s (%s/3).", symbol, trigger.trigger_type.value, actual_count)
            state_changed = True

    if state_changed:
        changed_on_disk = save_state(config.state_path, state)
        LOGGER.info("State %s.", "updated" if changed_on_disk else "unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
