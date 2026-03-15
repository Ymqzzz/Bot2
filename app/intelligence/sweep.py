from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, LiquidityState, StructureState, SweepState


class SweepEngine:
    def compute(self, data: EngineInput, structure: StructureState, liquidity: LiquidityState) -> SweepState:
        bars = data.bars[-6:]
        last = bars[-1]
        prior = bars[-2]
        nearest = liquidity.nearest_zones[0] if liquidity.nearest_zones else None
        sweep_detected = False
        sweep_type = "none"
        interpretation = "none"
        rejection = 0.0

        if nearest:
            breached_up = prior["high"] <= nearest.level < last["high"]
            breached_down = prior["low"] >= nearest.level > last["low"]
            if breached_up or breached_down:
                sweep_detected = True
                wick = (last["high"] - max(last["open"], last["close"])) if breached_up else (min(last["open"], last["close"]) - last["low"])
                body = abs(last["close"] - last["open"])
                rejection = clamp(wick / max(1e-6, body + wick))
                closed_back = (breached_up and last["close"] < nearest.level) or (breached_down and last["close"] > nearest.level)
                continuation = not closed_back and structure.displacement_strength > 0.45
                if closed_back and rejection > 0.55:
                    sweep_type = "external_liquidity_sweep_rejection"
                    interpretation = "stop_run_into_reversal"
                elif continuation:
                    sweep_type = "external_liquidity_sweep_continuation"
                    interpretation = "stop_run_into_expansion"
                else:
                    sweep_type = "failed_sweep"
                    interpretation = "ambiguous"

        rev_prob = clamp(0.65 * rejection + 0.35 * (1.0 - structure.displacement_strength)) if sweep_detected else 0.0
        cont_prob = clamp(0.7 * structure.displacement_strength + 0.3 * (1.0 - rejection)) if sweep_detected else 0.0
        rationale = [
            Evidence("rejection_strength", 0.5, rejection, "wick/body rejection after breach"),
            Evidence("displacement_strength", 0.5, structure.displacement_strength, "post-breach follow-through"),
        ]
        return SweepState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=clamp(max(rev_prob, cont_prob)),
            sources=["bars", "liquidity", "structure"],
            rationale=rationale,
            sweep_detected=sweep_detected,
            sweep_type=sweep_type,
            interpretation=interpretation,
            reversal_probability=rev_prob,
            continuation_probability=cont_prob,
            rejection_strength=rejection,
        )
