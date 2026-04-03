from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.adaptive.adaptive_types import AdversaryReport
from app.intelligence.adaptive.adversarial_path_generator import AdversarialPathGenerator
from app.intelligence.adaptive.fragility_under_attack_score import FragilityUnderAttackScore
from app.intelligence.adaptive.trade_attack_surface import TradeAttackSurface


@dataclass
class SyntheticAdversaryEngine:
    attack_surface_model: TradeAttackSurface = TradeAttackSurface()
    path_generator: AdversarialPathGenerator = AdversarialPathGenerator()
    fragility_scorer: FragilityUnderAttackScore = FragilityUnderAttackScore()

    def evaluate(self, *, context: dict) -> AdversaryReport:
        attack_surface = self.attack_surface_model.score(
            liquidity_thin=float(context.get("liquidity_thin_score", 0.2)),
            event_risk=float(context.get("event_risk_score", 0.2)),
            regime_instability=float(context.get("regime_instability", 0.3)),
        )
        ranked = self.path_generator.generate(attack_surface=attack_surface)
        resilience = float(context.get("resilience_score", 0.5))
        fragility = self.fragility_scorer.score(top_modes=ranked, resilience=resilience)

        adjustments: list[str] = []
        if fragility > 0.65:
            adjustments.extend(["tighten_initial_risk", "prefer_passive_entries", "delay_confirmation"])
        elif fragility > 0.45:
            adjustments.extend(["reduce_size", "require_followthrough_confirmation"])
        else:
            adjustments.append("standard_risk_protocol")

        return AdversaryReport(
            fragility_score=fragility,
            survives_review=fragility < 0.7,
            top_failure_modes=[m for m, _ in ranked[:3]],
            defensive_adjustments=adjustments,
        )
