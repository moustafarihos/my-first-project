"""A small client for the Deribit API (testnet only)."""

import json
import urllib.error
import urllib.parse
import urllib.request

# The bot only ever talks to the testnet, where all money is fake.
TESTNET_URL = "https://test.deribit.com/api/v2"


class DeribitError(Exception):
    pass


class DeribitClient:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: str | None = None

    @property
    def has_keys(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _call(self, method: str, params: dict, private: bool = False):
        query = urllib.parse.urlencode(
            {k: str(v).lower() if isinstance(v, bool) else v for k, v in params.items()}
        )
        request = urllib.request.Request(f"{TESTNET_URL}/{method}?{query}")
        if private:
            if self.token is None:
                self.authenticate()
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            body = json.load(exc)
        except urllib.error.URLError as exc:
            raise DeribitError(f"{method}: could not reach Deribit ({exc.reason})") from exc
        if "error" in body:
            raise DeribitError(f"{method}: {body['error']}")
        return body["result"]

    def authenticate(self) -> None:
        if not self.has_keys:
            raise DeribitError("Set DERIBIT_CLIENT_ID and DERIBIT_CLIENT_SECRET first")
        result = self._call(
            "public/auth",
            {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        self.token = result["access_token"]

    # Public market data

    def get_instruments(self, currency: str) -> list[dict]:
        return self._call(
            "public/get_instruments", {"currency": currency, "kind": "option", "expired": False}
        )

    def get_book_summaries(self, currency: str) -> list[dict]:
        return self._call(
            "public/get_book_summary_by_currency", {"currency": currency, "kind": "option"}
        )

    # Private account data and orders

    def get_equity(self, currency: str) -> float:
        summary = self._call("private/get_account_summary", {"currency": currency}, private=True)
        return summary["equity"]

    def get_option_positions(self, currency: str) -> list[dict]:
        return self._call(
            "private/get_positions", {"currency": currency, "kind": "option"}, private=True
        )

    def place_order(self, side: str, instrument: str, amount: float, price: float) -> dict:
        """Place a fill-or-kill limit order: it fills completely right away, or not at all."""
        result = self._call(
            f"private/{side}",
            {
                "instrument_name": instrument,
                "amount": amount,
                "type": "limit",
                "price": price,
                "time_in_force": "fill_or_kill",
                "label": "options_bot",
            },
            private=True,
        )
        return result["order"]
