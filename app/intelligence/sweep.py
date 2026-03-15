from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, LiquidityState, StructureState, SweepState


class SweepEngine:
    def compute(self, data: EngineInput, structure: StructureState, liquidity: LiquidityState) -> SweepState:
        bars = data.bars[-8:]
        last = bars[-1]
        prior = bars[-2]
        pool = next((z for z in liquidity.all_pools if z.pool_id == liquidity.most_significant_pool), None)
        if pool is None and liquidity.nearest_zones:
            pool = liquidity.nearest_zones[0]

        sweep_detected = False
        sweep_type = "non_sweep_breakout"
        interpretation = "none"
        breach_depth = 0.0
        rejection = 0.0
        acceptance = 0.0
        follow_through = 0.0

        if pool:
            up_breach = prior["high"] <= pool.price_level < last["high"]
            down_breach = prior["low"] >= pool.price_level > last["low"]
            if up_breach or down_breach:
                sweep_detected = True
                breach_depth = abs((last["high"] if up_breach else pool.price_level) - (pool.price_level if up_breach else last["low"]))
                range_size = max(1e-6, last["high"] - last["low"])
                close_back = (up_breach and last["close"] < pool.price_level) or (down_breach and last["close"] > pool.price_level)
                close_beyond = (up_breach and last["close"] > pool.price_level) or (down_breach and last["close"] < pool.price_level)
                wick = (last["high"] - max(last["open"], last["close"])) if up_breach else (min(last["open"], last["close"]) - last["low"])
                body = abs(last["close"] - last["open"])
                rejection = clamp((wick / max(1e-6, body + wick)) * (1.0 if close_back else 0.6))
                acceptance = clamp((body / range_size) * (1.0 if close_beyond else 0.5))
                follow_close = bars[-3:]
                impulse = abs(follow_close[-1]["close"] - follow_close[0]["close"]) / max(1e-6, range_size)
                follow_through = clamp(impulse)
                is_external = "prior_day" in pool.pool_type or "visible_range" in pool.pool_type

                if rejection > 0.55 and close_back and follow_through > 0.2:
                    sweep_type = "external_sweep_rejection" if is_external else "internal_sweep_rejection"
                    interpretation = "stop_run_into_reversal"
                elif acceptance > 0.55 and close_beyond and follow_through > 0.35:
                    sweep_type = "external_sweep_acceptance" if is_external else "internal_sweep_acceptance"
                    interpretation = "stop_run_into_expansion"
                elif breach_depth < (range_size * 0.15) and follow_through < 0.2:
                    sweep_type = "ambiguous_breach"
                    interpretation = "ambiguous"
                elif close_beyond:
                    sweep_type = "failed_breakout_after_sweep" if rejection > 0.4 else "non_sweep_breakout"
                    interpretation = "acceptance"
                else:
                    sweep_type = "ambiguous_breach"
                    interpretation = "ambiguous"

        rev_prob = clamp(0.65 * rejection + 0.35 * structure.reversal_quality_score)
        cont_prob = clamp(0.65 * acceptance + 0.35 * structure.continuation_quality_score)
        sweep_conf = clamp(max(rev_prob, cont_prob) * (0.7 + 0.3 * (1.0 - structure.messiness_penalty))) if sweep_detected else 0.0

        return SweepState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=sweep_conf,
            sources=["bars", "liquidity", "structure"],
            rationale=[
                Evidence("breach_depth", 0.2, breach_depth, "depth beyond pool"),
                Evidence("rejection", 0.3, rejection, "close-back and wick rejection"),
                Evidence("acceptance", 0.3, acceptance, "body-close acceptance"),
                Evidence("follow_through", 0.2, follow_through, "post-breach displacement"),
            ],
            sweep_detected=sweep_detected,
            sweep_type=sweep_type,
            interpretation=interpretation,
            reversal_probability=rev_prob,
            continuation_probability=cont_prob,
            rejection_strength=rejection,
            breached_pool_id=pool.pool_id if pool and sweep_detected else "",
            breach_depth=breach_depth,
            acceptance_strength=acceptance,
            follow_through_score=follow_through,
            post_sweep_state=interpretation,
            sweep_confidence=sweep_conf,
        )
