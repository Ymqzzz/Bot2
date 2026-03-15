from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Direction, Evidence, StructureEvent, StructureState


class StructureEngine:
    def compute(self, data: EngineInput) -> StructureState:
        bars = data.bars[-80:]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        closes = [b["close"] for b in bars]
        if len(closes) < 15:
            return StructureState(timestamp=data.timestamp, instrument=data.instrument, trace_id=data.trace_id, structure_label="insufficient")

        recent_high = max(highs[-20:])
        recent_low = min(lows[-20:])
        prior_high = max(highs[-50:-20]) if len(highs) > 50 else highs[0]
        prior_low = min(lows[-50:-20]) if len(lows) > 50 else lows[0]
        recent_range = max(1e-6, recent_high - recent_low)

        bos_up = 1.0 if closes[-1] > prior_high else 0.0
        bos_down = 1.0 if closes[-1] < prior_low else 0.0
        failed_breakout = 1.0 if (max(highs[-6:]) > prior_high and closes[-1] < prior_high) or (min(lows[-6:]) < prior_low and closes[-1] > prior_low) else 0.0

        trend_direction = Direction.BULLISH if closes[-1] > closes[-20] else Direction.BEARISH if closes[-1] < closes[-20] else Direction.NEUTRAL
        displacement = clamp(abs(closes[-1] - closes[-6]) / recent_range)
        overlap = float(data.features.get("bar_overlap", 0.5))
        compression = clamp(overlap * (1.0 - displacement))
        reclaim = clamp((0.75 * failed_breakout) + (0.25 if (bos_up == 0 and bos_down == 0 and displacement > 0.4) else 0.0))
        messiness_penalty = clamp(0.7 * overlap + 0.3 * failed_breakout)
        cleanliness = clamp(1.0 - messiness_penalty + 0.25 * displacement)

        continuation_quality = clamp(0.6 * displacement + 0.4 * (1.0 - failed_breakout))
        reversal_quality = clamp(0.55 * reclaim + 0.45 * (1.0 - continuation_quality))

        if failed_breakout and reclaim > 0.65:
            phase = "reclaim_phase"
        elif compression > 0.6 and closes[-1] < prior_high:
            phase = "compression_under_level"
        elif compression > 0.6 and closes[-1] > prior_low:
            phase = "compression_above_level"
        elif max(bos_up, bos_down) and continuation_quality > 0.6:
            phase = "expansion_leg"
        elif max(bos_up, bos_down) and continuation_quality <= 0.6:
            phase = "failed_continuation"
        elif cleanliness < 0.4:
            phase = "distribution_chop"
        else:
            phase = "pullback_leg"

        transition = f"{data.context.get('prior_phase', 'unknown')}->{phase}" if data.context.get("prior_phase") else "none"
        narrative = f"{phase}|trend={trend_direction.value}|bos_up={bos_up:.0f}|bos_down={bos_down:.0f}|failed={failed_breakout:.0f}"
        label = "trend_continuation" if continuation_quality > 0.62 else "failed_breakout" if failed_breakout else "chop_structure" if cleanliness < 0.42 else "range_structure"

        events = [
            StructureEvent("bos_up", Direction.BULLISH, bos_up, prior_high),
            StructureEvent("bos_down", Direction.BEARISH, bos_down, prior_low),
            StructureEvent("failed_breakout", Direction.NEUTRAL, failed_breakout, closes[-1]),
            StructureEvent("compression", Direction.NEUTRAL, compression, closes[-1]),
            StructureEvent("reclaim", trend_direction, reclaim, closes[-1]),
        ]
        rationale = [
            Evidence("displacement", 0.25, displacement, "impulse relative to local range"),
            Evidence("compression", 0.25, compression, "bar overlap and stalled progression"),
            Evidence("reclaim", 0.25, reclaim, "break-and-reclaim sequence quality"),
            Evidence("messiness", 0.25, messiness_penalty, "noise/chop penalty"),
        ]

        return StructureState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=clamp(0.5 * cleanliness + 0.5 * max(continuation_quality, reversal_quality)),
            sources=["bars", "features"],
            rationale=rationale,
            structure_label=label,
            trend_direction=trend_direction,
            displacement_strength=displacement,
            cleanliness_score=cleanliness,
            support_resistance={"support": [prior_low, recent_low], "resistance": [prior_high, recent_high]},
            events=events,
            current_phase=phase,
            phase_confidence=clamp(max(continuation_quality, reversal_quality)),
            recent_phase_transition=transition,
            structural_narrative=narrative,
            continuation_quality_score=continuation_quality,
            reversal_quality_score=reversal_quality,
            compression_score=compression,
            reclaim_score=reclaim,
            messiness_penalty=messiness_penalty,
        )
