from __future__ import annotations


class TradeIntentReport:
    def build(self, *, candidate_strategy: str, order_style: str, invalidations: list[str]) -> dict[str, object]:
        return {
            "strategy": candidate_strategy,
            "order_style": order_style,
            "invalidations": invalidations,
        }
