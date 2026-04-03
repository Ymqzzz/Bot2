from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdaptiveInputContract:
    min_account_equity: float = 1.0
    min_notional: float = 1.0

    def normalize_context(self, context: dict) -> dict:
        normalized = dict(context)
        normalized.setdefault("account_equity", 100_000.0)
        normalized.setdefault("free_margin", float(normalized["account_equity"]) * 0.65)
        normalized.setdefault("candidate_notional", float(normalized["account_equity"]) * 0.1)
        normalized.setdefault("effective_leverage", 10.0)
        normalized.setdefault("queued_trades", [])
        normalized.setdefault("execution_records", [])
        normalized.setdefault("adaptive_memory_window", 20)
        normalized.setdefault("strategy_concentration", 0.2)
        normalized.setdefault("correlation_stress", 0.2)
        normalized["account_equity"] = max(self.min_account_equity, float(normalized["account_equity"]))
        normalized["candidate_notional"] = max(self.min_notional, float(normalized["candidate_notional"]))
        return normalized

    def normalize_features(self, features: dict[str, float]) -> dict[str, float]:
        normalized = dict(features)
        normalized.setdefault("realized_vol", 0.2)
        normalized.setdefault("atr_percentile", 0.5)
        normalized.setdefault("directional_persistence", 0.5)
        normalized.setdefault("spread_percentile", 0.5)
        normalized.setdefault("volatility_noise", 0.3)
        return normalized
