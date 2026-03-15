from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, LiquidityState, LiquidityZone, StructureState


class LiquidityEngine:
    def _touch_count(self, levels: list[float], anchor: float, tolerance: float) -> int:
        return sum(1 for x in levels if abs(x - anchor) <= tolerance)

    def compute(self, data: EngineInput, structure: StructureState) -> LiquidityState:
        bars = data.bars[-120:]
        current = float(bars[-1]["close"])
        highs = [float(b["high"]) for b in bars]
        lows = [float(b["low"]) for b in bars]
        span = max(1e-6, max(highs) - min(lows))
        tolerance = span * 0.02

        pool_specs = [
            ("prior_day_high", max(highs[-48:]), 0.9),
            ("prior_day_low", min(lows[-48:]), 0.9),
            ("session_high", max(highs[-24:]), 0.75),
            ("session_low", min(lows[-24:]), 0.75),
            ("visible_range_high", max(highs), 0.65),
            ("visible_range_low", min(lows), 0.65),
            ("round_number", round(current, 3), 0.55),
        ]

        zones: list[LiquidityZone] = []
        for idx, (ptype, level, base_visibility) in enumerate(pool_specs):
            distance = abs(current - level)
            distance_score = 1.0 / (1.0 + 8.0 * distance / span)
            touch_count = self._touch_count(highs + lows, level, tolerance)
            cluster_density = clamp(touch_count / 8.0)
            recency_hits = self._touch_count([*highs[-20:], *lows[-20:]], level, tolerance)
            recency_score = clamp(recency_hits / 4.0)
            round_confluence = 1.0 if abs(level - round(level, 3)) <= span * 0.01 else 0.0
            structural_confluence = 1.0 if any(abs(level - sr) <= tolerance for sr in structure.support_resistance.get("support", []) + structure.support_resistance.get("resistance", [])) else 0.0

            significance = clamp(
                0.30 * base_visibility
                + 0.20 * cluster_density
                + 0.20 * recency_score
                + 0.15 * structural_confluence
                + 0.15 * round_confluence
            )
            sweep_risk = clamp(significance * (0.5 + 0.5 * distance_score))
            target_likelihood = clamp(0.6 * significance + 0.4 * distance_score)
            zones.append(
                LiquidityZone(
                    pool_id=f"{ptype}_{idx}",
                    pool_type=ptype,
                    level=level,
                    distance=distance,
                    significance=significance,
                    visibility_score=base_visibility,
                    cluster_density_score=cluster_density,
                    recency_score=recency_score,
                    touch_count=touch_count,
                    sweep_risk_score=sweep_risk,
                    target_likelihood_score=target_likelihood,
                )
            )

        by_distance = sorted(zones, key=lambda z: z.distance)
        by_significance = sorted(zones, key=lambda z: (z.significance, z.target_likelihood_score), reverse=True)
        nearest_up = next((z for z in by_distance if z.level >= current), None)
        nearest_down = next((z for z in by_distance if z.level < current), None)
        most_significant = by_significance[0] if by_significance else None
        target = most_significant.pool_type if most_significant else "none"
        pressure = clamp(sum(z.target_likelihood_score for z in by_significance[:3]) / 3.0) if by_significance else 0.0

        up_pressure = sum(z.target_likelihood_score for z in by_significance[:3] if z.level >= current)
        down_pressure = sum(z.target_likelihood_score for z in by_significance[:3] if z.level < current)
        direction = "upside" if up_pressure > down_pressure + 0.05 else "downside" if down_pressure > up_pressure + 0.05 else "balanced"
        label = "high_signal" if pressure > 0.72 else "mixed" if pressure > 0.45 else "muted"

        rationale = [
            Evidence("liquidity_pressure", 0.5, pressure, "ranked significance + target likelihood"),
            Evidence("most_significant_pool", 0.3, most_significant.significance if most_significant else 0.0, "importance independent from proximity"),
            Evidence("structure_confluence", 0.2, structure.cleanliness_score, "liquidity alignment with structure"),
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
            target_hypothesis=target,
            nearest_zones=by_significance,
            nearest_upside_pool=nearest_up.pool_id if nearest_up else "none",
            nearest_downside_pool=nearest_down.pool_id if nearest_down else "none",
            most_significant_pool=most_significant.pool_id if most_significant else "none",
            current_liquidity_target_hypothesis=target,
            liquidity_pressure_direction=direction,
            liquidity_context_label=label,
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
