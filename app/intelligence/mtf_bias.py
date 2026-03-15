from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Direction, Evidence, MultiTimeframeBiasState, TimeframeBias


class MultiTimeframeBiasEngine:
    TIMEFRAMES = ("4h", "1h", "15m", "5m", "1m")

    def _frame_bias(self, f: dict[str, float], tf: str) -> TimeframeBias:
        slope = float(f.get(f"{tf}_slope", 0.0))
        momentum = clamp(float(f.get(f"{tf}_momentum", 0.5)))
        structure = clamp(float(f.get(f"{tf}_structure_quality", 0.5)))
        persistence = clamp(float(f.get(f"{tf}_persistence", 0.5)))
        trend_quality = clamp(0.55 * persistence + 0.45 * (1.0 - abs(slope - 0.5)))
        direction = Direction.BULLISH if slope > 0.55 else Direction.BEARISH if slope < 0.45 else Direction.NEUTRAL
        confidence = clamp(0.4 * trend_quality + 0.3 * structure + 0.3 * momentum)
        return TimeframeBias(tf, direction, confidence, trend_quality, structure, momentum)

    def compute(self, data: EngineInput) -> MultiTimeframeBiasState:
        frames = [self._frame_bias(data.features, tf) for tf in self.TIMEFRAMES]
        htf = frames[0:2]
        setup = frames[2:4]
        trigger = frames[4]

        def dominant(group: list[TimeframeBias]) -> Direction:
            score = sum(1 if g.direction == Direction.BULLISH else -1 if g.direction == Direction.BEARISH else 0 for g in group)
            return Direction.BULLISH if score > 0 else Direction.BEARISH if score < 0 else Direction.NEUTRAL

        htf_bias = dominant(htf)
        setup_bias = dominant(setup)
        trigger_bias = trigger.direction
        aligned = int(htf_bias != Direction.NEUTRAL and htf_bias == setup_bias) + int(setup_bias == trigger_bias and setup_bias != Direction.NEUTRAL)
        alignment_score = clamp((aligned / 2.0) * sum(f.confidence for f in frames) / len(frames))
        conflict_score = clamp(1.0 - alignment_score)
        alignment_label = "aligned" if alignment_score > 0.7 else "partially_aligned" if alignment_score > 0.45 else "conflicted" if conflict_score > 0.65 else "neutral"

        rationale = [
            Evidence("htf_bias", 0.4, 1.0 if htf_bias == Direction.BULLISH else -1.0 if htf_bias == Direction.BEARISH else 0.0, "higher timeframe direction"),
            Evidence("setup_bias", 0.35, 1.0 if setup_bias == Direction.BULLISH else -1.0 if setup_bias == Direction.BEARISH else 0.0, "mid timeframe setup context"),
            Evidence("trigger_bias", 0.25, 1.0 if trigger_bias == Direction.BULLISH else -1.0 if trigger_bias == Direction.BEARISH else 0.0, "lower timeframe trigger context"),
        ]

        return MultiTimeframeBiasState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=1.0 - conflict_score,
            sources=["features"],
            rationale=rationale,
            frame_bias=frames,
            htf_bias=htf_bias,
            setup_bias=setup_bias,
            trigger_bias=trigger_bias,
            alignment_score=alignment_score,
            conflict_score=conflict_score,
            alignment_label=alignment_label,
        )
