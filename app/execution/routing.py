from __future__ import annotations

from execution_engine import choose_entry_type


def choose_order_type(strategy: str, breakout_mag: float, liquidity_factor: float, spread_pctile: float) -> str:
    return choose_entry_type(strategy=strategy, breakout_mag=breakout_mag, liquidity_factor=liquidity_factor, spread_pctile=spread_pctile)
