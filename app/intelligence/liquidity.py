from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, LiquidityState, LiquidityZone, StructureState


class LiquidityEngine:
    def _cluster_score(self, levels: list[float], center: float, threshold: float = 0.0004) -> tuple[float, int]:
        touches = sum(1 for level in levels if abs(level - center) <= threshold)
        return clamp(touches / 5.0), touches

    def _zone(self, bars: list[dict], current: float, pool_type: str, level: float, base_visibility: float, idx: int) -> LiquidityZone:
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        hi_cluster, hi_touches = self._cluster_score(highs, level)
        lo_cluster, lo_touches = self._cluster_score(lows, level)
        cluster_density = max(hi_cluster, lo_cluster)
        touch_count = max(hi_touches, lo_touches)
        round_confluence = 1.0 if abs(level - round(level, 2)) < 0.00015 else 0.0
        recency = clamp(1.0 - idx / 50.0)
        distance = abs(current - level)
        distance_score = clamp(1.0 - (distance / 0.008))
        significance = clamp(
            0.35 * base_visibility + 0.25 * cluster_density + 0.15 * recency + 0.15 * round_confluence + 0.10 * distance_score
        )
        return LiquidityZone(
            pool_id=f"{pool_type}:{level:.5f}",
            pool_type=pool_type,
            price_level=level,
            distance_from_current_price=distance,
            significance_score=significance,
            visibility_score=base_visibility,
            cluster_density_score=cluster_density,
            recency_score=recency,
            touch_count=touch_count,
            sweep_risk_score=clamp(0.6 * cluster_density + 0.4 * base_visibility),
            target_likelihood_score=clamp(0.7 * significance + 0.3 * distance_score),
        )

    def compute(self, data: EngineInput, structure: StructureState) -> LiquidityState:
        bars = data.bars[-120:]
        current = bars[-1]["close"]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        prior_day_high = max(highs[-48:])
        prior_day_low = min(lows[-48:])
        session_high = max(highs[-24:])
        session_low = min(lows[-24:])
        range_high = max(highs)
        range_low = min(lows)

        pools = [
            self._zone(bars, current, "prior_day_high", prior_day_high, 0.95, 0),
            self._zone(bars, current, "prior_day_low", prior_day_low, 0.95, 0),
            self._zone(bars, current, "session_high", session_high, 0.80, 3),
            self._zone(bars, current, "session_low", session_low, 0.80, 3),
            self._zone(bars, current, "visible_range_high", range_high, 0.70, 10),
            self._zone(bars, current, "visible_range_low", range_low, 0.70, 10),
            self._zone(bars, current, "round_number", round(current, 2), 0.65, 1),
        ]

        pools_by_distance = sorted(pools, key=lambda x: x.distance_from_current_price)
        pools_by_sig = sorted(pools, key=lambda x: x.significance_score, reverse=True)
        nearest_up = next((p for p in pools_by_distance if p.price_level >= current), None)
        nearest_down = next((p for p in pools_by_distance if p.price_level <= current), None)
        top = pools_by_sig[0] if pools_by_sig else None
        pressure = clamp(sum(p.target_likelihood_score for p in pools_by_distance[:3]) / 3.0)
        if nearest_up and nearest_down:
            direction = "upside" if nearest_up.target_likelihood_score > nearest_down.target_likelihood_score else "downside"
        else:
            direction = "neutral"
        context_label = "high_significance" if top and top.significance_score > 0.75 else "mixed"

        rationale = [
            Evidence("top_pool_significance", 0.5, top.significance_score if top else 0.0, "importance separated from distance"),
            Evidence("liquidity_pressure", 0.5, pressure, "aggregate nearest-pool target pressure"),
        ]

        return LiquidityState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=clamp(0.55 + 0.35 * pressure + 0.1 * structure.cleanliness_score),
            sources=["bars", "structure"],
            rationale=rationale,
            pressure_score=pressure,
            target_hypothesis=top.pool_type if top else "none",
            nearest_zones=pools_by_distance[:5],
            nearest_upside_pool=nearest_up.pool_id if nearest_up else "",
            nearest_downside_pool=nearest_down.pool_id if nearest_down else "",
            most_significant_pool=top.pool_id if top else "",
            current_liquidity_target_hypothesis=top.pool_type if top else "none",
            liquidity_pressure_direction=direction,
            liquidity_context_label=context_label,
            all_pools=pools_by_sig,
        )
