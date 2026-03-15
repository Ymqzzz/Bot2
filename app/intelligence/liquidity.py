from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, LiquidityState, LiquidityZone, StructureState


class LiquidityEngine:
    def compute(self, data: EngineInput, structure: StructureState) -> LiquidityState:
        bars = data.bars or []
        closes = [float(b.get("close", 0.0)) for b in bars] or [0.0]
        highs = [float(b.get("high", closes[i])) for i, b in enumerate(bars)] or closes
        lows = [float(b.get("low", closes[i])) for i, b in enumerate(bars)] or closes
        last = closes[-1]

        zone_near = LiquidityZone(
            pool_id="near_pool",
            pool_type="local",
            level=last,
            distance=0.0,
            significance=0.4,
            price_level=last,
            distance_from_current_price=0.0,
            significance_score=0.4,
        )
        zone_major = LiquidityZone(
            pool_id="major_pool",
            pool_type="swing",
            level=max(highs[-20:]),
            distance=abs(max(highs[-20:]) - last),
            significance=0.8,
            price_level=max(highs[-20:]),
            distance_from_current_price=abs(max(highs[-20:]) - last),
            significance_score=0.8,
        )

        pressure = clamp(0.6 * structure.cleanliness_score + 0.4 * float(data.features.get("directional_persistence", 0.5)))
        context = "high_signal" if pressure > 0.65 else "neutral"

        return LiquidityState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=pressure,
            sources=["bars", "structure"],
            rationale=[Evidence("pressure", 1.0, pressure, "structure-guided liquidity pressure")],
            pressure_score=pressure,
            target_hypothesis="continuation" if pressure > 0.55 else "mean_revert",
            nearest_zones=[zone_near, zone_major],
            nearest_upside_pool=zone_major.pool_id,
            nearest_downside_pool="near_pool",
            most_significant_pool=zone_major.pool_id,
            current_liquidity_target_hypothesis="continuation" if pressure > 0.55 else "none",
            liquidity_pressure_direction="bullish" if structure.trend_direction.value == "bullish" else "bearish",
            liquidity_context_label=context,
            all_pools=[zone_major, zone_near],
        )
