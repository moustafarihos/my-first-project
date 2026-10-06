"""Choosing a put spread. Everything here is pure math, so it is easy to test."""

import math
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Settings:
    currency: str = "BTC"
    # Only look at options that expire between these many days from now.
    min_days: int = 7
    max_days: int = 21
    # Sell the put whose delta is closest to this (0.20 is roughly a 20% chance of finishing in the money).
    short_delta: float = 0.20
    # Buy a protective put this many dollars lower.
    width_usd: float = 2000
    # Contracts per leg, in BTC. 0.1 is Deribit's minimum.
    amount: float = 0.1
    # Skip trades that pay less than this share of the width.
    min_credit_ratio: float = 0.15
    # Never risk more than this on one spread.
    max_loss_usd: float = 300
    # How many spreads may be open at once.
    max_open_spreads: int = 1
    # Stop trading once equity falls this far below where it started.
    max_drawdown: float = 0.20


@dataclass
class Option:
    name: str
    strike: float
    expiry: datetime
    bid: float  # in BTC
    ask: float  # in BTC
    iv: float  # implied volatility, as a fraction (0.55 = 55%)
    underlying: float  # in USD


@dataclass
class PutSpread:
    short: Option
    long: Option
    amount: float

    @property
    def width_usd(self) -> float:
        return self.short.strike - self.long.strike

    @property
    def credit_usd(self) -> float:
        # Deribit quotes option prices in BTC, so convert with the underlying price.
        return (self.short.bid - self.long.ask) * self.short.underlying * self.amount

    @property
    def max_loss_usd(self) -> float:
        return self.width_usd * self.amount - self.credit_usd


def put_delta(underlying: float, strike: float, iv: float, years: float) -> float:
    """Black-76 delta of a put. It is between -1 and 0."""
    d1 = (math.log(underlying / strike) + 0.5 * iv * iv * years) / (iv * math.sqrt(years))
    return 0.5 * (1 + math.erf(d1 / math.sqrt(2))) - 1


def parse_options(instruments: list[dict], summaries: list[dict]) -> list[Option]:
    """Join instrument details with live prices, keeping only puts that can be traded."""
    books = {s["instrument_name"]: s for s in summaries}
    options = []
    for inst in instruments:
        book = books.get(inst["instrument_name"])
        if inst["option_type"] != "put" or not book:
            continue
        if not book.get("bid_price") or not book.get("ask_price") or not book.get("mark_iv"):
            continue
        options.append(
            Option(
                name=inst["instrument_name"],
                strike=inst["strike"],
                expiry=datetime.fromtimestamp(inst["expiration_timestamp"] / 1000, timezone.utc),
                bid=book["bid_price"],
                ask=book["ask_price"],
                iv=book["mark_iv"] / 100,
                underlying=book["underlying_price"],
            )
        )
    return options


def choose_spread(
    options: list[Option], settings: Settings, now: datetime
) -> tuple[PutSpread | None, str]:
    """Pick a put spread, or return None and the reason nothing fit."""
    expiries = sorted(
        {o.expiry for o in options if settings.min_days <= (o.expiry - now).days <= settings.max_days}
    )
    if not expiries:
        return None, f"no expiry between {settings.min_days} and {settings.max_days} days away"
    expiry = expiries[0]
    puts = [o for o in options if o.expiry == expiry]
    years = (expiry - now).total_seconds() / (365 * 24 * 3600)

    short = min(
        puts,
        key=lambda o: abs(abs(put_delta(o.underlying, o.strike, o.iv, years)) - settings.short_delta),
    )
    candidates = [o for o in puts if o.strike <= short.strike - settings.width_usd]
    if not candidates:
        return None, f"no strike at least ${settings.width_usd:,.0f} below {short.name}"
    long = max(candidates, key=lambda o: o.strike)

    spread = PutSpread(short=short, long=long, amount=settings.amount)
    if spread.credit_usd < settings.min_credit_ratio * spread.width_usd * settings.amount:
        return None, f"credit ${spread.credit_usd:.2f} is too small for the risk"
    if spread.max_loss_usd > settings.max_loss_usd:
        return None, f"max loss ${spread.max_loss_usd:.2f} is above the ${settings.max_loss_usd:.0f} limit"
    return spread, "ok"


def drawdown_exceeded(start_equity: float, equity: float, settings: Settings) -> bool:
    return equity < start_equity * (1 - settings.max_drawdown)


def count_open_spreads(positions: list[dict]) -> int:
    """Each spread has exactly one short leg, so count short positions."""
    return sum(1 for p in positions if p["size"] < 0)
