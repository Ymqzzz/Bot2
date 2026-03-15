from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Direction, Evidence, StructureEvent, StructureState


class StructureEngine:
    def compute(self, data: EngineInput) -> StructureState:
        bars = data.bars or []
        if len(bars) < 2:
            return StructureState(
                timestamp=data.timestamp,
                instrument=data.instrument,
                trace_id=data.trace_id,
                confidence=0.0,
                sources=["bars"],
                rationale=[Evidence("bars", 1.0, 0.0, "insufficient bars")],
                current_phase="unknown",
                structural_narrative="insufficient_structure",
            )

        closes = [float(b.get("close", 0.0)) for b in bars]
        highs = [float(b.get("high", c)) for b, c in zip(bars, closes)]
        lows = [float(b.get("low", c)) for b, c in zip(bars, closes)]
        up_moves = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i - 1])
        persistence = up_moves / max(1, len(closes) - 1)
        overlap = float(data.features.get("bar_overlap", 0.5))
        displacement = abs(closes[-1] - closes[0])
        range_size = max(highs) - min(lows)
        trend_strength = displacement / max(range_size, 1e-9)

        if persistence > 0.62 and overlap < 0.45:
            phase = "expansion_leg"
        elif persistence < 0.38 and overlap < 0.55:
            phase = "reversal_probe"
        else:
            phase = "range_rotation"

        direction = Direction.BULLISH if closes[-1] > closes[0] else Direction.BEARISH if closes[-1] < closes[0] else Direction.NEUTRAL
        cleanliness = clamp(0.55 * (1.0 - overlap) + 0.45 * float(data.features.get("directional_persistence", persistence)))

        return StructureState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=cleanliness,
            sources=["bars", "features"],
            rationale=[Evidence("cleanliness", 1.0, cleanliness, "overlap + persistence")],
            structure_label="trend" if phase == "expansion_leg" else "mixed",
            trend_direction=direction,
            displacement_strength=clamp(trend_strength),
            cleanliness_score=cleanliness,
            support_resistance={"support": [min(lows[-20:])], "resistance": [max(highs[-20:])]},
            events=[StructureEvent(event_type="phase", direction=direction, strength=cleanliness, level=closes[-1])],
            current_phase=phase,
            phase_confidence=cleanliness,
            recent_phase_transition="none",
            structural_narrative=phase,
            continuation_quality_score=cleanliness,
            reversal_quality_score=clamp(1.0 - cleanliness),
            compression_score=clamp(overlap),
            reclaim_score=clamp(float(data.features.get("breakout_follow_through", 0.5))),
            messiness_penalty=clamp(overlap),
        )
