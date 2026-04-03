from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdaptivePolicy:
    min_capital_efficiency: float = 0.25
    min_edge_trust: float = 0.2
    max_adversary_fragility: float = 0.7
    max_negotiation_penalty: float = 0.65

    @classmethod
    def from_context(cls, context: dict) -> "AdaptivePolicy":
        cfg = context.get("adaptive_policy", {})
        return cls(
            min_capital_efficiency=float(cfg.get("min_capital_efficiency", 0.25)),
            min_edge_trust=float(cfg.get("min_edge_trust", 0.2)),
            max_adversary_fragility=float(cfg.get("max_adversary_fragility", 0.7)),
            max_negotiation_penalty=float(cfg.get("max_negotiation_penalty", 0.65)),
        )
