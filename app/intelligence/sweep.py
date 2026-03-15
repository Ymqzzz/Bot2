from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, LiquidityState, StructureState, SweepState


class SweepEngine:
    def compute(self, data: EngineInput, structure: StructureState, liquidity: LiquidityState) -> SweepState:
        bars = data.bars[-8:]
        last, prior = bars[-1], bars[-2]
        pool = next((z for z in liquidity.nearest_zones if z.pool_id == liquidity.most_significant_pool), None)
        if pool is None and liquidity.nearest_zones:
            pool = liquidity.nearest_zones[0]

        sweep_detected = False
        sweep_type = "non_sweep_breakout"
        interpretation = "none"
        rejection = acceptance = follow = depth = 0.0
        breached_pool_id = None

        if pool:
            breached_up = prior["high"] <= pool.level < last["high"]
            breached_down = prior["low"] >= pool.level > last["low"]
            if breached_up or breached_down:
                sweep_detected = True
                breached_pool_id = pool.pool_id
                extreme = last["high"] if breached_up else last["low"]
                depth = abs(extreme - pool.level)
                full_range = max(1e-6, last["high"] - last["low"])
                depth_norm = clamp(depth / full_range)
                wick = (last["high"] - max(last["open"], last["close"])) if breached_up else (min(last["open"], last["close"]) - last["low"])
                body = abs(last["close"] - last["open"])
                rejection = clamp(wick / max(1e-6, wick + body))

                close_beyond = (breached_up and last["close"] > pool.level) or (breached_down and last["close"] < pool.level)
                close_back_within = (breached_up and last["close"] <= pool.level) or (breached_down and last["close"] >= pool.level)
                impulse = abs(last["close"] - prior["close"]) / max(1e-6, full_range)
                follow = clamp(0.55 * structure.displacement_strength + 0.45 * impulse)
                acceptance = clamp((0.55 if close_beyond else 0.0) + 0.45 * follow - 0.25 * rejection)

                if close_back_within and rejection > 0.58 and follow < 0.55:
                    sweep_type = "external_sweep_rejection"
                    interpretation = "stop_run_into_reversal"
                elif close_beyond and acceptance > 0.6:
                    sweep_type = "external_sweep_acceptance"
                    interpretation = "stop_run_into_expansion"
                elif depth_norm < 0.22 and follow < 0.4:
                    sweep_type = "ambiguous_breach"
                    interpretation = "ambiguous_breach"
                elif close_beyond and follow > 0.5:
                    sweep_type = "non_sweep_breakout"
                    interpretation = "post_breakout_acceptance"
                else:
                    sweep_type = "failed_breakout_after_sweep"
                    interpretation = "failed_breakout_after_sweep"

        reversal_probability = clamp(0.55 * rejection + 0.25 * (1.0 - follow) + 0.2 * (1.0 - structure.continuation_quality_score)) if sweep_detected else 0.0
        continuation_probability = clamp(0.55 * acceptance + 0.3 * follow + 0.15 * structure.continuation_quality_score) if sweep_detected else 0.0
        post_state = interpretation if sweep_detected else "none"
        confidence = clamp(max(reversal_probability, continuation_probability) * (0.65 + 0.35 * (1.0 - float(data.features.get("spread_percentile", 0.5)))))

        rationale = [
            Evidence("rejection_strength", 0.35, rejection, "wick/body rejection after liquidity breach"),
            Evidence("acceptance_strength", 0.35, acceptance, "close-location + follow-through acceptance"),
            Evidence("follow_through_score", 0.30, follow, "post-breach displacement and momentum"),
        ]
        return SweepState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=confidence,
            sources=["bars", "liquidity", "structure"],
            rationale=rationale,
            sweep_detected=sweep_detected,
            sweep_type=sweep_type,
            interpretation=interpretation,
            reversal_probability=reversal_probability,
            continuation_probability=continuation_probability,
            rejection_strength=rejection,
            breached_pool_id=breached_pool_id,
            breach_depth=depth,
            acceptance_strength=acceptance,
            follow_through_score=follow,
            post_sweep_state=post_state,
            sweep_confidence=confidence,
        )
