from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, LiquidityState, LiquidityZone, StructureState


class LiquidityEngine:
    def compute(self, data: EngineInput, structure: StructureState) -> LiquidityState:
        bars = data.bars[-100:]
        current = bars[-1]["close"]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        pd_high = max(highs[-48:])
        pd_low = min(lows[-48:])
        session_high = max(highs[-24:])
        session_low = min(lows[-24:])
        round_number = round(current, 2)

        levels = [
            ("prior_day_high", pd_high, 0.9),
            ("prior_day_low", pd_low, 0.9),
            ("session_high", session_high, 0.7),
            ("session_low", session_low, 0.7),
            ("round_number", round_number, 0.6),
        ]
        zones = []
        for ztype, level, sig in levels:
            dist = abs(current - level)
            zones.append(LiquidityZone(ztype, level, dist, clamp(sig * (1.0 / (1.0 + 1000 * dist)))))
        zones = sorted(zones, key=lambda z: z.distance)
        pressure = clamp(sum(z.significance for z in zones[:3]))
        target = zones[0].zone_type if zones else "none"
        rationale = [
            Evidence("nearest_zone_distance", 0.5, zones[0].distance if zones else 0.0, "distance to nearest likely stop pool"),
            Evidence("pressure", 0.5, pressure, "aggregate significance of nearby pools"),
        ]
        return LiquidityState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=clamp(0.6 * pressure + 0.4 * structure.cleanliness_score),
            sources=["bars", "structure"],
            rationale=rationale,
            pressure_score=pressure,
            target_hypothesis=target,
            nearest_zones=zones[:5],
        )
