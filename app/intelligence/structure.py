from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Direction, Evidence, StructureEvent, StructureState


class StructureEngine:
    def compute(self, data: EngineInput) -> StructureState:
        bars = data.bars[-60:]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        closes = [b["close"] for b in bars]
        if len(closes) < 12:
            return StructureState(timestamp=data.timestamp, instrument=data.instrument, trace_id=data.trace_id, structure_label="insufficient")

        recent_high = max(highs[-20:])
        recent_low = min(lows[-20:])
        prior_high = max(highs[-40:-20]) if len(highs) >= 40 else highs[0]
        prior_low = min(lows[-40:-20]) if len(lows) >= 40 else lows[0]
        overlap = float(data.features.get("bar_overlap", 0.5))
        persistence = float(data.features.get("directional_persistence", 0.5))

        bos_up = 1.0 if closes[-1] > prior_high else 0.0
        bos_down = 1.0 if closes[-1] < prior_low else 0.0
        failed_breakout = 1.0 if (max(highs[-6:]) > prior_high and closes[-1] < prior_high) or (min(lows[-6:]) < prior_low and closes[-1] > prior_low) else 0.0
        reclaim = 1.0 if failed_breakout and ((closes[-1] > prior_high and closes[-2] < prior_high) or (closes[-1] < prior_low and closes[-2] > prior_low)) else 0.0
        displacement = clamp(abs(closes[-1] - closes[-6]) / max(1e-6, recent_high - recent_low))
        compression = clamp(overlap * (1.0 - displacement))
        messiness = clamp(0.6 * overlap + 0.4 * (1.0 - persistence))
        cleanliness = clamp(1.0 - messiness - 0.25 * failed_breakout + 0.2 * displacement)

        if compression > 0.65 and closes[-1] < prior_high:
            phase = "compression_under_level"
        elif compression > 0.65 and closes[-1] > prior_low:
            phase = "compression_above_level"
        elif reclaim > 0.5:
            phase = "reclaim_phase"
        elif failed_breakout > 0.5:
            phase = "failed_continuation"
        elif bos_up or bos_down:
            phase = "expansion_leg"
        elif messiness > 0.6:
            phase = "distribution_chop"
        else:
            phase = "pullback_leg" if persistence > 0.55 else "range_rotation"

        trend_direction = Direction.BULLISH if closes[-1] > closes[0] else Direction.BEARISH if closes[-1] < closes[0] else Direction.NEUTRAL
        continuation_quality = clamp(0.6 * displacement + 0.4 * persistence - 0.25 * failed_breakout)
        reversal_quality = clamp(0.6 * reclaim + 0.4 * failed_breakout)

        return StructureState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=clamp(0.6 * cleanliness + 0.4 * displacement),
            sources=["bars", "features"],
            rationale=[
                Evidence("compression", 0.2, compression, "overlap-driven compression"),
                Evidence("displacement", 0.3, displacement, "impulse from prior leg"),
                Evidence("failed_breakout", 0.2, failed_breakout, "break-and-reject state"),
                Evidence("messiness", 0.3, messiness, "narrative noise penalty"),
            ],
            structure_label=phase,
            trend_direction=trend_direction,
            displacement_strength=displacement,
            cleanliness_score=cleanliness,
            support_resistance={"support": [prior_low, recent_low], "resistance": [prior_high, recent_high]},
            events=[
                StructureEvent("bos_up", Direction.BULLISH, bos_up, prior_high),
                StructureEvent("bos_down", Direction.BEARISH, bos_down, prior_low),
                StructureEvent("failed_breakout", Direction.NEUTRAL, failed_breakout, closes[-1]),
                StructureEvent("reclaim", trend_direction, reclaim, closes[-1]),
            ],
            current_phase=phase,
            phase_confidence=clamp(0.5 + 0.5 * max(continuation_quality, reversal_quality)),
            recent_phase_transition="from_failed_breakout" if reclaim else "stable",
            structural_narrative=f"{phase} with {'clean' if cleanliness > 0.6 else 'messy'} tape",
            continuation_quality_score=continuation_quality,
            reversal_quality_score=reversal_quality,
            compression_score=compression,
            reclaim_score=reclaim,
            messiness_penalty=messiness,
        )
