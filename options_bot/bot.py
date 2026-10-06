"""Run one round of the bot: check the account, then open a put spread if allowed.

Usage:
    python -m options_bot.bot           # dry run: shows what it would do
    python -m options_bot.bot --trade   # places orders on the Deribit testnet
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from options_bot.deribit import DeribitClient, DeribitError
from options_bot.strategy import (
    PutSpread,
    Settings,
    choose_spread,
    count_open_spreads,
    drawdown_exceeded,
    parse_options,
)

STATE_FILE = Path(__file__).parent / "state.json"

log = logging.getLogger("options_bot")


def load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(state: dict, path: Path) -> None:
    path.write_text(json.dumps(state, indent=2))


def check_account(client: DeribitClient, settings: Settings, state_path: Path) -> bool:
    """Apply the account-wide safety rules. Returns True if a new trade is allowed."""
    equity = client.get_equity(settings.currency)
    state = load_state(state_path)
    if "start_equity" not in state:
        state["start_equity"] = equity
        save_state(state, state_path)
    log.info("Equity: %.4f %s (started at %.4f)", equity, settings.currency, state["start_equity"])

    if drawdown_exceeded(state["start_equity"], equity, settings):
        log.error("Kill switch: equity fell more than %.0f%%. Not trading.", settings.max_drawdown * 100)
        return False

    open_spreads = count_open_spreads(client.get_option_positions(settings.currency))
    if open_spreads >= settings.max_open_spreads:
        log.info("%d spread(s) already open. Waiting for them to expire.", open_spreads)
        return False
    return True


def open_spread(client: DeribitClient, spread: PutSpread) -> bool:
    # Buy the protective put first, so we are never left holding only the risky short put.
    long_order = client.place_order("buy", spread.long.name, spread.amount, spread.long.ask)
    if long_order["order_state"] != "filled":
        log.warning("Protective put did not fill (%s). Nothing was traded.", long_order["order_state"])
        return False
    short_order = client.place_order("sell", spread.short.name, spread.amount, spread.short.bid)
    if short_order["order_state"] != "filled":
        log.warning(
            "Short put did not fill (%s). You now hold only the protective put %s.",
            short_order["order_state"],
            spread.long.name,
        )
        return False
    return True


def run_once(
    client: DeribitClient,
    settings: Settings,
    trade: bool,
    state_path: Path = STATE_FILE,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)

    if client.has_keys:
        if not check_account(client, settings, state_path):
            return "skipped"
    elif trade:
        raise DeribitError("Set DERIBIT_CLIENT_ID and DERIBIT_CLIENT_SECRET to trade")
    else:
        log.info("No API keys set, so skipping account checks (dry run only).")

    options = parse_options(
        client.get_instruments(settings.currency), client.get_book_summaries(settings.currency)
    )
    spread, reason = choose_spread(options, settings, now)
    if spread is None:
        log.info("No trade: %s", reason)
        return "no_trade"

    log.info(
        "Plan: sell %s at %.4f, buy %s at %.4f, %.1f %s each. "
        "Credit $%.2f, max loss $%.2f.",
        spread.short.name,
        spread.short.bid,
        spread.long.name,
        spread.long.ask,
        spread.amount,
        settings.currency,
        spread.credit_usd,
        spread.max_loss_usd,
    )
    if not trade:
        log.info("Dry run: no orders placed. Add --trade to place them on the testnet.")
        return "dry_run"
    return "opened" if open_spread(client, spread) else "failed"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sell BTC put spreads on the Deribit testnet.")
    parser.add_argument("--trade", action="store_true", help="place real testnet orders")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = DeribitClient(os.environ.get("DERIBIT_CLIENT_ID"), os.environ.get("DERIBIT_CLIENT_SECRET"))
    try:
        run_once(client, Settings(), trade=args.trade)
    except DeribitError as exc:
        log.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
