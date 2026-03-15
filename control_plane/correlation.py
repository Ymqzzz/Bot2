from __future__ import annotations

from functools import lru_cache

import pandas as pd


def _split(instr: str) -> tuple[str, str]:
    p = instr.replace("/", "_").split("_")
    return p[0], p[1]


@lru_cache(maxsize=16)
def _macro_key(instrument: str, side: str) -> str:
    b, q = _split(instrument)
    sign = 1 if side.upper() == "BUY" else -1
    if b == "USD":
        sign *= -1
    if q == "USD":
        return "anti_usd" if sign > 0 else "pro_usd"
    if "JPY" in (b, q):
        return "rates_sensitive_jpy"
    if instrument == "XAU_USD":
        return "gold_real_rate_expression"
    return "risk_on_fx" if sign > 0 else "risk_off_fx"


class CorrelationEngine:
    def build_correlation_matrix(self, instruments, lookback: dict[str, list[float]] | pd.DataFrame) -> dict[str, dict[str, float]]:
        if isinstance(lookback, pd.DataFrame):
            df = lookback[instruments]
        else:
            df = pd.DataFrame({i: lookback.get(i, []) for i in instruments})
        corr = df.corr().fillna(0.0)
        return {k: {k2: float(v2) for k2, v2 in row.items()} for k, row in corr.to_dict().items()}

    def cluster_macro_expression(self, candidate) -> str:
        side = candidate.side if hasattr(candidate, "side") else candidate.get("side", "BUY")
        ins = candidate.instrument if hasattr(candidate, "instrument") else candidate.get("instrument", "")
        return _macro_key(ins, side)

    def compute_portfolio_overlap(self, candidate, open_positions, correlation_matrix) -> float:
        ins = candidate.instrument if hasattr(candidate, "instrument") else candidate.get("instrument")
        overlap = 0.0
        for p in open_positions:
            other = p.get("instrument")
            risk = abs(float(p.get("risk", p.get("risk_fraction", 0.0)) or 0.0))
            overlap += abs(correlation_matrix.get(ins, {}).get(other, 0.0)) * risk
        return overlap

    def compute_currency_exposure(self, candidate) -> dict[str, float]:
        ins = candidate.instrument if hasattr(candidate, "instrument") else candidate.get("instrument", "")
        side = candidate.side if hasattr(candidate, "side") else candidate.get("side", "BUY")
        b, q = _split(ins)
        sign = 1.0 if side.upper() == "BUY" else -1.0
        return {b: sign, q: -sign}
