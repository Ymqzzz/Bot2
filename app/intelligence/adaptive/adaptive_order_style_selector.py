from __future__ import annotations


class AdaptiveOrderStyleSelector:
    def choose(self, *, passive_score: float, aggressive_score: float) -> str:
        if passive_score >= aggressive_score + 0.05:
            return "passive_limit"
        if aggressive_score >= passive_score + 0.05:
            return "aggressive_marketable"
        return "hybrid_child_orders"
