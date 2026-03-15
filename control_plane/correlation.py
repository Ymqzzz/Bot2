from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import numpy as np


class CorrelationEngine:
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {"ts": datetime.min.replace(tzinfo=timezone.utc), "matrix": {}}

    def build_correlation_matrix(self, instruments: dict[str, list[float]], lookback: int) -> dict[str, dict[str, float]]:
        now = datetime.now(timezone.utc)
        if (now - self._cache["ts"]) < timedelta(minutes=5) and self._cache["matrix"]:
            return self._cache["matrix"]
        matrix: dict[str, dict[str, float]] = {}
        keys = sorted(instruments.keys())
        for a in keys:
            matrix[a] = {}
            ra = np.array(instruments[a][-lookback:], dtype=float)
            for b in keys:
                rb = np.array(instruments[b][-lookback:], dtype=float)
                n = min(len(ra), len(rb))
                if n < 5:
                    corr = 0.0
                else:
                    corr = float(np.corrcoef(ra[-n:], rb[-n:])[0, 1])
                    if np.isnan(corr):
                        corr = 0.0
                matrix[a][b] = max(-1.0, min(1.0, corr))
        self._cache = {"ts": now, "matrix": matrix}
        return matrix

    def cluster_macro_expression(self, candidate: dict) -> str:
        ins = candidate.get("instrument", "")
        side = candidate.get("side", "BUY")
        base, quote = ins.split("_") if "_" in ins else (ins[:3], ins[3:])
        sign = 1 if side == "BUY" else -1
        if "XAU" in ins:
            return "gold_real_rate_expression"
        if base == "USD" and sign > 0 or quote == "USD" and sign < 0:
            return "pro_usd"
        if base == "USD" and sign < 0 or quote == "USD" and sign > 0:
            return "anti_usd"
        if "JPY" in ins:
            return "rates_sensitive_jpy"
        return "risk_on_fx"

    def compute_portfolio_overlap(self, candidate: dict, open_positions: list[dict], correlation_matrix: dict[str, dict[str, float]]) -> float:
        ins = candidate.get("instrument")
        overlap = 0.0
        for p in open_positions:
            p_ins = p.get("instrument")
            units = abs(float(p.get("units", 0.0)))
            corr = abs(correlation_matrix.get(ins, {}).get(p_ins, 0.0))
            overlap += corr * min(1.0, units / 100000)
        return float(min(1.0, overlap))

    def compute_currency_exposure(self, candidate: dict) -> dict[str, float]:
        ins = candidate.get("instrument", "")
        side = candidate.get("side", "BUY")
        r = float(candidate.get("risk_fraction_requested", 0.0) or 0.0)
        base, quote = ins.split("_") if "_" in ins else (ins[:3], ins[3:])
        sign = 1.0 if side == "BUY" else -1.0
        return {base: sign * r, quote: -sign * r}
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
