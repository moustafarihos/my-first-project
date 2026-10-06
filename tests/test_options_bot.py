from datetime import datetime, timedelta, timezone

import pytest

from options_bot.bot import run_once
from options_bot.deribit import DeribitError
from options_bot.strategy import (
    Settings,
    choose_spread,
    count_open_spreads,
    drawdown_exceeded,
    parse_options,
    put_delta,
)

NOW = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)
EXPIRY = NOW + timedelta(days=10)
PRICE = 100_000


def make_market(strikes=range(80_000, 101_000, 1_000), expiry=EXPIRY):
    """Fake Deribit data: puts at 55% IV, priced so lower strikes are cheaper."""
    instruments, summaries = [], []
    for strike in strikes:
        name = f"BTC-{expiry:%d%b%y}-{strike}-P".upper()
        instruments.append(
            {
                "instrument_name": name,
                "option_type": "put",
                "strike": strike,
                "expiration_timestamp": expiry.timestamp() * 1000,
            }
        )
        mid = max(0.0005, (strike - 80_000) / 400_000)
        summaries.append(
            {
                "instrument_name": name,
                "bid_price": mid - 0.0002,
                "ask_price": mid + 0.0002,
                "mark_iv": 55,
                "underlying_price": PRICE,
            }
        )
    return instruments, summaries


class FakeClient:
    def __init__(self, has_keys=True, equity=1.0, positions=(), fill=True):
        self.has_keys = has_keys
        self.equity = equity
        self.positions = list(positions)
        self.fill = fill
        self.orders = []
        self.instruments, self.summaries = make_market()

    def get_equity(self, currency):
        return self.equity

    def get_option_positions(self, currency):
        return self.positions

    def get_instruments(self, currency):
        return self.instruments

    def get_book_summaries(self, currency):
        return self.summaries

    def place_order(self, side, instrument, amount, price):
        self.orders.append((side, instrument, amount, price))
        return {"order_state": "filled" if self.fill else "cancelled"}


def test_put_delta_is_minus_half_at_the_money_and_smaller_further_out():
    assert put_delta(PRICE, PRICE, 0.55, 1e-9) == pytest.approx(-0.5, abs=0.01)
    assert -0.5 < put_delta(PRICE, 90_000, 0.55, 10 / 365) < 0


def test_parse_options_skips_calls_and_missing_prices():
    instruments, summaries = make_market(strikes=[90_000, 95_000])
    instruments.append({**instruments[0], "instrument_name": "CALL", "option_type": "call"})
    summaries[1]["bid_price"] = 0
    options = parse_options(instruments, summaries)
    assert [o.strike for o in options] == [90_000]
    assert options[0].iv == 0.55


def test_choose_spread_sells_about_20_delta_and_buys_2000_lower():
    spread, reason = choose_spread(parse_options(*make_market()), Settings(), NOW)
    assert reason == "ok"
    years = 10 / 365
    delta = put_delta(PRICE, spread.short.strike, 0.55, years)
    assert abs(delta) == pytest.approx(0.20, abs=0.05)
    assert spread.width_usd == 2000
    assert 0 < spread.credit_usd < spread.width_usd * spread.amount
    assert spread.max_loss_usd == pytest.approx(200 - spread.credit_usd)


def test_choose_spread_needs_an_expiry_in_range():
    options = parse_options(*make_market(expiry=NOW + timedelta(days=60)))
    spread, reason = choose_spread(options, Settings(), NOW)
    assert spread is None
    assert "no expiry" in reason


def test_choose_spread_respects_max_loss():
    spread, reason = choose_spread(parse_options(*make_market()), Settings(max_loss_usd=50), NOW)
    assert spread is None
    assert "max loss" in reason


def test_choose_spread_rejects_tiny_credit():
    settings = Settings(min_credit_ratio=0.9)
    spread, reason = choose_spread(parse_options(*make_market()), settings, NOW)
    assert spread is None
    assert "too small" in reason


def test_drawdown_and_open_spread_counting():
    settings = Settings(max_drawdown=0.2)
    assert not drawdown_exceeded(1.0, 0.85, settings)
    assert drawdown_exceeded(1.0, 0.75, settings)
    assert count_open_spreads([{"size": -0.1}, {"size": 0.1}]) == 1


def test_dry_run_places_no_orders(tmp_path):
    client = FakeClient()
    assert run_once(client, Settings(), trade=False, state_path=tmp_path / "s.json", now=NOW) == "dry_run"
    assert client.orders == []


def test_dry_run_works_without_keys(tmp_path):
    client = FakeClient(has_keys=False)
    assert run_once(client, Settings(), trade=False, state_path=tmp_path / "s.json", now=NOW) == "dry_run"


def test_trading_needs_keys(tmp_path):
    with pytest.raises(DeribitError):
        run_once(FakeClient(has_keys=False), Settings(), trade=True, state_path=tmp_path / "s.json", now=NOW)


def test_trade_buys_protection_before_selling(tmp_path):
    client = FakeClient()
    assert run_once(client, Settings(), trade=True, state_path=tmp_path / "s.json", now=NOW) == "opened"
    assert [side for side, *_ in client.orders] == ["buy", "sell"]
    long_strike = int(client.orders[0][1].split("-")[2])
    short_strike = int(client.orders[1][1].split("-")[2])
    assert long_strike == short_strike - 2000


def test_no_short_sale_when_protection_does_not_fill(tmp_path):
    client = FakeClient(fill=False)
    assert run_once(client, Settings(), trade=True, state_path=tmp_path / "s.json", now=NOW) == "failed"
    assert [side for side, *_ in client.orders] == ["buy"]


def test_kill_switch_stops_trading(tmp_path):
    state = tmp_path / "s.json"
    client = FakeClient(equity=1.0)
    run_once(client, Settings(), trade=False, state_path=state, now=NOW)
    client.equity = 0.7
    assert run_once(client, Settings(), trade=True, state_path=state, now=NOW) == "skipped"
    assert client.orders == []


def test_waits_while_a_spread_is_open(tmp_path):
    client = FakeClient(positions=[{"size": -0.1}, {"size": 0.1}])
    assert run_once(client, Settings(), trade=True, state_path=tmp_path / "s.json", now=NOW) == "skipped"
    assert client.orders == []
