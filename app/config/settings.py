from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class BotSettings:
    instruments: list[str]
    granularity: str
    min_signal_score: float
    max_spread_pctile: float
    max_positions: int
    risk_budget_daily: float
    cluster_risk_cap: float
    min_trade_interval_sec: int
    max_trade_interval_sec: int

    @staticmethod
    def from_env() -> "BotSettings":
        instruments = os.environ.get("INSTRUMENTS_JSON", "EUR_USD,USD_JPY,GBP_USD").replace('"', "")
        parsed = [x.strip() for x in instruments.replace("[", "").replace("]", "").split(",") if x.strip()]
        return BotSettings(
            instruments=parsed,
            granularity=os.environ.get("GRANULARITY", "M5"),
            min_signal_score=float(os.environ.get("MIN_SIGNAL_SCORE", "0.15")),
            max_spread_pctile=float(os.environ.get("MAX_SPREAD_PCTILE", "85")),
            max_positions=int(os.environ.get("MAX_POSITIONS", "6")),
            risk_budget_daily=float(os.environ.get("RISK_BUDGET_DAILY", "0.015")),
            cluster_risk_cap=float(os.environ.get("CLUSTER_RISK_CAP", "0.01")),
            min_trade_interval_sec=int(os.environ.get("MIN_TRADE_INTERVAL_SEC", "5")),
            max_trade_interval_sec=int(os.environ.get("MAX_TRADE_INTERVAL_SEC", "120")),
        )
