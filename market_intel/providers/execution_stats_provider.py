from __future__ import annotations

from typing import Callable, Dict, Optional

import numpy as np

from .base import BaseExecutionStatsProvider, ProviderResult


class ExecutionStatsProvider(BaseExecutionStatsProvider):
    """Normalize execution quality from fills and in-memory spread/slippage history."""

    def __init__(
        self,
        *,
        tx_fetcher: Callable[[], dict],
        price_cache: Dict[str, float],
        execution_stats: Optional[object] = None,
    ) -> None:
        self.tx_fetcher = tx_fetcher
        self.price_cache = price_cache
        self.execution_stats = execution_stats

    def get_execution_stats(self, *, n: int = 100) -> ProviderResult[dict]:
        tx = self.tx_fetcher() or {}
        fills = [t for t in tx.get("transactions", []) if t.get("type") == "ORDER_FILL"][-int(n) :]

        normalized = []
        slips = []
        for fill in fills:
            try:
                instrument = fill.get("instrument", "")
                fill_price = float(fill.get("price", 0.0))
                mid = float(self.price_cache.get(instrument, fill_price) or fill_price)
                slip = abs(fill_price - mid) / max(mid, 1e-9)
                slips.append(slip)
                normalized.append({"instrument": instrument, "fill_price": fill_price, "mid_ref": mid, "slippage": slip})
            except Exception:
                continue

        if not normalized:
            return ProviderResult(ok=False, status="unavailable", source="execution_stats", error="No fill data")

        by_instr = {}
        if self.execution_stats is not None:
            for item in normalized:
                instr = item["instrument"]
                if instr not in by_instr:
                    try:
                        by_instr[instr] = self.execution_stats.summary(instr)
                    except Exception:
                        by_instr[instr] = {}

        return ProviderResult(
            ok=True,
            data={
                "fills_analyzed": len(normalized),
                "slippage_mean": float(np.mean(slips)),
                "slippage_p95": float(np.quantile(slips, 0.95)),
                "per_instrument": by_instr,
            },
            status="ok",
            source="execution_stats",
        )
