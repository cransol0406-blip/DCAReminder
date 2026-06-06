from __future__ import annotations

from datetime import datetime
import logging

from dca_reminder.config import load_config
from dca_reminder.market_calendar import ET, get_market_window
from dca_reminder.market_data import fetch_market_data
from dca_reminder.rules import (
    STRATEGY_PARAMS,
    SignalType,
    count_confirmed_drop_levels,
    evaluate_intraday_signals,
    next_daily_trigger_price,
    next_monthly_trigger_price,
)
from dca_reminder.state import (
    apply_sent_signals,
    get_day_state,
    get_month_state,
    get_symbol_state,
    get_week_state,
    load_state,
    save_state,
)
from dca_reminder.telegram import (
    build_daily_summary_message,
    build_intraday_message,
    build_monthly_summary_message,
    build_weekly_summary_message,
    send_message,
)


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def main() -> int:
    config = load_config()
    now = datetime.now(ET)
    window = get_market_window(now)
    if not window.is_trading_day:
        LOGGER.info("Not a NYSE trading day; exiting.")
        return 0
    if not (window.is_regular_window or window.is_close_summary_window):
        LOGGER.info("Outside monitoring windows; exiting.")
        return 0

    state = load_state(config.state_path)
    state_changed = False

    for symbol in config.symbols:
        params = STRATEGY_PARAMS.get(symbol)
        if params is None:
            LOGGER.warning("Skipping unsupported symbol %s.", symbol)
            continue

        try:
            market_data = fetch_market_data(symbol, now, include_current_price=window.is_regular_window)
        except Exception as exc:
            LOGGER.warning("Skipping %s because market data failed: %s", symbol, exc)
            continue

        symbol_state = get_symbol_state(state, symbol)
        day_state = get_day_state(symbol_state, window.day_key)
        month_state = get_month_state(symbol_state, window.month_key, market_data.previous_month_close)
        week_state = get_week_state(symbol_state, window.week_key)

        if window.is_regular_window:
            snapshot = market_data.intraday_snapshot()
            signals = evaluate_intraday_signals(
                snapshot=snapshot,
                params=params,
                day_state=day_state,
                month_state=month_state,
                week_state=week_state,
                is_weekly_open_reminder_window=window.is_weekly_open_reminder_window,
            )
            if signals:
                message = build_intraday_message(snapshot, params, signals)
                _deliver_message(config, message)
                apply_sent_signals(day_state, month_state, week_state, signals, snapshot.timestamp.isoformat())
                LOGGER.info("%s sent %s intraday signal(s).", symbol, len(signals))
                state_changed = True
            else:
                LOGGER.info("%s has no new intraday signals.", symbol)

        if window.is_close_summary_window:
            close_snapshot = market_data.close_snapshot()
            if close_snapshot is None:
                LOGGER.info("%s close price is not ready; summary will retry later.", symbol)
            else:
                next_daily_price = next_daily_trigger_price(close_snapshot.price, params)
                next_monthly_price = next_monthly_trigger_price(month_state, params)

                if not day_state.get("daily_summary_sent"):
                    confirmed_daily = count_confirmed_drop_levels(
                        close_snapshot.price,
                        close_snapshot.previous_close,
                        params.daily_drop_pct,
                    )
                    confirmed_monthly = count_confirmed_drop_levels(
                        close_snapshot.price,
                        close_snapshot.previous_month_close,
                        params.monthly_drop_pct,
                    )
                    confirmed_ma20 = close_snapshot.price <= close_snapshot.ma20 * params.ma20_factor
                    confirmed_ma50 = close_snapshot.price <= close_snapshot.ma50 * params.ma50_factor
                    daily_message = build_daily_summary_message(
                        snapshot=close_snapshot,
                        params=params,
                        day_state=day_state,
                        confirmed_daily_count=confirmed_daily,
                        confirmed_monthly_count=confirmed_monthly,
                        confirmed_ma20=confirmed_ma20,
                        confirmed_ma50=confirmed_ma50,
                        tomorrow_daily_trigger_price=next_daily_price,
                        next_monthly_trigger_price=next_monthly_price,
                    )
                    _deliver_message(config, daily_message)
                    day_state["daily_summary_sent"] = True
                    LOGGER.info("%s sent daily summary.", symbol)
                    state_changed = True

                if window.is_week_last_trading_day and not week_state.get("weekly_summary_sent"):
                    weekly_message = build_weekly_summary_message(
                        snapshot=close_snapshot,
                        params=params,
                        week_key=window.week_key,
                        week_state=week_state,
                        next_week_daily_trigger_price=next_daily_price,
                        next_monthly_trigger_price=next_monthly_price,
                    )
                    _deliver_message(config, weekly_message)
                    week_state["weekly_summary_sent"] = True
                    LOGGER.info("%s sent weekly summary.", symbol)
                    state_changed = True

                if window.is_month_last_trading_day and not month_state.get("monthly_summary_sent"):
                    monthly_message = build_monthly_summary_message(close_snapshot, params, month_state)
                    _deliver_message(config, monthly_message)
                    month_state["monthly_summary_sent"] = True
                    LOGGER.info("%s sent monthly summary.", symbol)
                    state_changed = True

    if state_changed:
        changed_on_disk = save_state(config.state_path, state)
        LOGGER.info("State %s.", "updated" if changed_on_disk else "unchanged")
    return 0


def _deliver_message(config, message: str) -> None:
    if config.dry_run:
        LOGGER.info("DRY_RUN Telegram message:\n%s", message)
        return
    if not config.telegram_bot_token or not config.telegram_chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
    send_message(config.telegram_bot_token, config.telegram_chat_id, message)


if __name__ == "__main__":
    raise SystemExit(main())
