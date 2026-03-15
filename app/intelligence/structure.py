from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Direction, Evidence, StructureEvent, StructureState


class StructureEngine:
    def compute(self, data: EngineInput) -> StructureState:
        bars = data.bars[-50:]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        closes = [b["close"] for b in bars]
        if len(closes) < 10:
            return StructureState(timestamp=data.timestamp, instrument=data.instrument, trace_id=data.trace_id, structure_label="insufficient")

        recent_high = max(highs[-15:])
        recent_low = min(lows[-15:])
        prior_high = max(highs[-35:-15]) if len(highs) > 35 else highs[0]
        prior_low = min(lows[-35:-15]) if len(lows) > 35 else lows[0]

        bos_up = 1.0 if closes[-1] > prior_high else 0.0
        bos_down = 1.0 if closes[-1] < prior_low else 0.0
        choch = 1.0 if (closes[-1] > prior_high and min(lows[-8:]) < prior_low) or (closes[-1] < prior_low and max(highs[-8:]) > prior_high) else 0.0

        trend_direction = Direction.BULLISH if closes[-1] > closes[0] else Direction.BEARISH if closes[-1] < closes[0] else Direction.NEUTRAL
        displacement = clamp(abs(closes[-1] - closes[-5]) / max(1e-6, recent_high - recent_low))
        range_width = max(1e-6, recent_high - recent_low)
        failed_breakout = 1.0 if (max(highs[-5:]) > prior_high and closes[-1] < prior_high) or (min(lows[-5:]) < prior_low and closes[-1] > prior_low) else 0.0
        cleanliness = clamp(1.0 - float(data.features.get("bar_overlap", 0.5)) - 0.35 * failed_breakout + 0.2 * displacement)

        label = "trend_continuation" if max(bos_up, bos_down) and failed_breakout == 0 else "failed_breakout" if failed_breakout else "chop_structure" if cleanliness < 0.4 else "range_structure"

        events = [
            StructureEvent("bos_up", Direction.BULLISH, bos_up, prior_high),
            StructureEvent("bos_down", Direction.BEARISH, bos_down, prior_low),
            StructureEvent("choch", trend_direction, choch, closes[-1]),
            StructureEvent("failed_breakout", Direction.NEUTRAL, failed_breakout, closes[-1]),
        ]
        rationale = [
            Evidence("displacement", 0.4, displacement, "impulse relative to range"),
            Evidence("failed_breakout", 0.3, failed_breakout, "break and reclaim detection"),
            Evidence("cleanliness", 0.3, cleanliness, "overlap-adjusted structure quality"),
        ]

        return StructureState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=clamp(0.6 * cleanliness + 0.4 * displacement),
            sources=["bars", "features"],
            rationale=rationale,
            structure_label=label,
            trend_direction=trend_direction,
            displacement_strength=displacement,
            cleanliness_score=cleanliness,
            support_resistance={"support": [prior_low, recent_low], "resistance": [prior_high, recent_high]},
            events=events,
        )
