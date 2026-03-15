from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence, RegimeState


class RegimeEngine:
    def compute(self, data: EngineInput) -> RegimeState:
        f = data.features
        atr_pct = clamp(float(f.get("atr_percentile", f.get("atr", 0.5))))
        realized_vol = clamp(float(f.get("realized_vol", 0.5)))
        overlap = clamp(float(f.get("bar_overlap", 0.5)))
        persistence = clamp(float(f.get("directional_persistence", 0.5)))
        breakout_follow = clamp(float(f.get("breakout_follow_through", 0.5)))
        spread_pct = clamp(float(f.get("spread_percentile", 0.2)))
        near_event = 1.0 if data.context.get("near_event", False) else 0.0

        trend = 0.45 * persistence + 0.35 * breakout_follow + 0.20 * (1.0 - overlap)
        compression = 0.45 * (1.0 - atr_pct) + 0.35 * overlap + 0.2 * (1.0 - breakout_follow)
        chop = 0.4 * overlap + 0.35 * (1.0 - persistence) + 0.25 * (1.0 - breakout_follow)
        instability = 0.45 * near_event + 0.35 * spread_pct + 0.2 * realized_vol
        expansion = 0.45 * atr_pct + 0.35 * breakout_follow + 0.2 * realized_vol

        score_vector = {
            "trend": clamp(trend),
            "compression": clamp(compression),
            "chop": clamp(chop),
            "post_event_instability": clamp(instability),
            "expansion": clamp(expansion),
            "range": clamp(0.5 * overlap + 0.5 * (1.0 - breakout_follow)),
        }

        label = max(score_vector, key=score_vector.get)
        if label == "trend" and trend < 0.55:
            label = "weak_trend"
        if label == "post_event_instability" and spread_pct > 0.8:
            label = "low_liquidity_instability"
        if breakout_follow > 0.72 and overlap < 0.35:
            label = "breakout_environment"

        confidence = clamp(max(score_vector.values()) - sorted(score_vector.values())[-2] + 0.5)
        rationale = [
            Evidence("atr_percentile", 0.25, atr_pct, "volatility regime input"),
            Evidence("bar_overlap", 0.25, overlap, "range/chop discriminator"),
            Evidence("directional_persistence", 0.25, persistence, "trend discriminator"),
            Evidence("breakout_follow_through", 0.25, breakout_follow, "expansion discriminator"),
        ]
        return RegimeState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=confidence,
            sources=["features"],
            rationale=rationale,
            label=label,
            score_vector=score_vector,
        )
