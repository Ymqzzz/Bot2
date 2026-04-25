from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import os
from typing import Any

import requests

from app.config.settings import BotSettings
from app.runtime.upgraded_bot import BrokerContext, UpgradedBot


@dataclass(frozen=True)
class OandaConfig:
    token: str
    account_id: str
    host: str

    @staticmethod
    def from_env() -> "OandaConfig":
        token = (os.environ.get("OANDA_API_TOKEN") or "").strip()
        account_id = (os.environ.get("OANDA_ACCOUNT_ID") or "").strip()
        environment = (os.environ.get("OANDA_ENV", "practice") or "practice").strip().lower()
        host = "https://api-fxpractice.oanda.com/v3" if environment != "live" else "https://api-fxtrade.oanda.com/v3"
        if not token or not account_id:
            raise RuntimeError("Missing OANDA_API_TOKEN or OANDA_ACCOUNT_ID in environment")
        return OandaConfig(token=token, account_id=account_id, host=host)


class OandaRestClient:
    def __init__(self, config: OandaConfig, timeout_sec: float = 10.0):
        self.config = config
        self.timeout_sec = timeout_sec
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.config.host}{path}"
        response = self.session.request(method=method, url=url, params=params, json=json, timeout=self.timeout_sec)
        response.raise_for_status()
        payload: dict[str, Any] = response.json() if response.content else {}
        return payload

    def get_account_summary(self) -> dict[str, Any]:
        return self._request("GET", f"/accounts/{self.config.account_id}/summary").get("account", {})

    def get_open_positions(self) -> list[dict[str, Any]]:
        payload = self._request("GET", f"/accounts/{self.config.account_id}/openPositions")
        return payload.get("positions", [])

    def get_candles(self, instrument: str, granularity: str, count: int) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/instruments/{instrument}/candles",
            params={"price": "M", "granularity": granularity, "count": int(count)},
        )
        return payload.get("candles", [])

    def get_price(self, instrument: str) -> dict[str, Any]:
        payload = self._request(
            "GET",
            f"/accounts/{self.config.account_id}/pricing",
            params={"instruments": instrument},
        )
        prices = payload.get("prices", [])
        return prices[0] if prices else {}

    def create_order(self, instrument: str, units: int) -> dict[str, Any]:
        body = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(int(units)),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }
        return self._request("POST", f"/accounts/{self.config.account_id}/orders", json=body)


class OandaMarketDataProvider:
    def __init__(self, client: OandaRestClient):
        self.client = client
        self._spread_hist: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=500))

    def get_recent_bars(self, instrument: str, granularity: str, count: int = 120) -> list[dict[str, Any]]:
        candles = self.client.get_candles(instrument, granularity, count)
        out: list[dict[str, Any]] = []
        for candle in candles:
            if not candle.get("complete"):
                continue
            mid = candle.get("mid") or {}
            out.append(
                {
                    "time": candle.get("time"),
                    "o": float(mid.get("o", 0.0)),
                    "h": float(mid.get("h", 0.0)),
                    "l": float(mid.get("l", 0.0)),
                    "c": float(mid.get("c", 0.0)),
                    "v": int(candle.get("volume", 0)),
                }
            )
        return out

    def get_spread_pctile(self, instrument: str) -> float:
        price = self.client.get_price(instrument)
        bids = price.get("bids") or [{}]
        asks = price.get("asks") or [{}]
        bid = float(bids[0].get("price", 0.0) or 0.0)
        ask = float(asks[0].get("price", 0.0) or 0.0)
        spread = max(0.0, ask - bid)
        hist = self._spread_hist[instrument]
        if spread > 0:
            hist.append(spread)
        if not hist:
            return 50.0
        latest = hist[-1]
        le = sum(1 for s in hist if s <= latest)
        return (le / len(hist)) * 100.0

    def get_liquidity_factor(self, instrument: str) -> float:
        spread_pctile = self.get_spread_pctile(instrument)
        return max(0.0, min(1.0, 1.0 - (spread_pctile / 100.0)))

    def has_near_event(self, instrument: str) -> bool:
        _ = instrument
        return False


class LiveTrader:
    def __init__(self, bot: UpgradedBot, market_data: OandaMarketDataProvider, broker: OandaRestClient):
        self.bot = bot
        self.market_data = market_data
        self.broker = broker

    def _broker_context(self) -> BrokerContext:
        summary = self.broker.get_account_summary()
        positions = self.broker.get_open_positions()
        nav = float(summary.get("NAV", summary.get("balance", 0.0)) or 0.0)
        unrealized = float(summary.get("unrealizedPL", 0.0) or 0.0)
        realized = float(summary.get("pl", 0.0) or 0.0)
        return BrokerContext(
            nav=nav,
            open_positions=positions,
            corr_matrix={},
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            equity_now=nav,
        )

    @staticmethod
    def _decision_signed_units(decision: dict[str, Any]) -> int:
        proposal = decision.get("proposal") or {}
        try:
            return int(proposal.get("signed_units", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def run_once(self) -> list[dict[str, Any]]:
        context = self._broker_context()
        decisions = self.bot.run_cycle(self.market_data, context)
        fills: list[dict[str, Any]] = []
        for decision in decisions:
            if not decision.get("approved"):
                continue
            proposal = decision.get("proposal") or {}
            instrument = str(proposal.get("instrument", "")).strip()
            units = self._decision_signed_units(decision)
            if not instrument or units == 0:
                continue
            order_response = self.broker.create_order(instrument, units)
            fills.append(
                {
                    "instrument": instrument,
                    "units": units,
                    "order_create_transaction": order_response.get("orderCreateTransaction", {}),
                    "order_fill_transaction": order_response.get("orderFillTransaction", {}),
                }
            )
        return fills


def run_live_cycle_once(settings: BotSettings | None = None) -> list[dict[str, Any]]:
    cfg = OandaConfig.from_env()
    client = OandaRestClient(cfg)
    bot = UpgradedBot(settings=settings or BotSettings.from_env())
    trader = LiveTrader(bot=bot, market_data=OandaMarketDataProvider(client), broker=client)
    return trader.run_once()


def main() -> None:
    fills = run_live_cycle_once()
    print({"submitted_orders": len(fills), "fills": fills})


if __name__ == "__main__":
    main()
