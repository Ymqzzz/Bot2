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
        directional_efficiency = clamp(float(f.get("directional_efficiency", persistence)))
        range_compression = clamp(float(f.get("range_compression", overlap)))
        pa_trend = clamp(float(f.get("price_action_trend_score", 0.5)))
        pa_mean_revert = clamp(float(f.get("price_action_mean_revert_score", 0.5)))
        pa_breakout = clamp(float(f.get("price_action_breakout_score", 0.5)))
        pa_confidence = clamp(float(f.get("price_action_confidence", 0.5)))
        pa_id = int(float(f.get("price_action_id", 0.0)))
        near_event = 1.0 if data.context.get("near_event", False) else 0.0

        trend = 0.35 * persistence + 0.25 * breakout_follow + 0.20 * (1.0 - overlap) + 0.20 * pa_trend
        compression = 0.40 * (1.0 - atr_pct) + 0.25 * overlap + 0.20 * range_compression + 0.15 * pa_mean_revert
        chop = 0.35 * overlap + 0.25 * (1.0 - persistence) + 0.20 * (1.0 - breakout_follow) + 0.20 * (1.0 - directional_efficiency)
        instability = 0.45 * near_event + 0.35 * spread_pct + 0.2 * realized_vol
        expansion = 0.35 * atr_pct + 0.25 * breakout_follow + 0.15 * realized_vol + 0.25 * pa_breakout

        score_vector = {
            "trend": clamp(trend),
            "compression": clamp(compression),
            "chop": clamp(chop),
            "post_event_instability": clamp(instability),
            "expansion": clamp(expansion),
            "range": clamp(0.40 * overlap + 0.35 * (1.0 - breakout_follow) + 0.25 * pa_mean_revert),
        }

        label = max(score_vector, key=score_vector.get)
        if label == "trend" and trend < 0.55:
            label = "weak_trend"
        if label == "post_event_instability" and spread_pct > 0.8:
            label = "low_liquidity_instability"
        if breakout_follow > 0.72 and overlap < 0.35:
            label = "breakout_environment"
        if pa_id == 3 and pa_confidence > 0.72 and expansion > 0.55:
            label = "algorithmic_breakout_expansion"
        elif pa_id == 2 and pa_confidence > 0.70 and compression > 0.50:
            label = "algorithmic_mean_reversion"
        elif pa_id == 1 and pa_confidence > 0.68 and trend > 0.54:
            label = "algorithmic_trend_continuation"

        ordered_scores = sorted(score_vector.values())
        margin = ordered_scores[-1] - ordered_scores[-2]
        stability = 0.5 * directional_efficiency + 0.5 * (1.0 - near_event)
        pa_alignment = max(0.0, 1.0 - abs(pa_trend - score_vector["trend"]) - abs(pa_breakout - score_vector["expansion"]) * 0.5)
        confidence = clamp(0.35 + 0.40 * margin + 0.15 * stability + 0.10 * pa_alignment)
        rationale = [
            Evidence("atr_percentile", 0.20, atr_pct, "volatility regime input"),
            Evidence("bar_overlap", 0.20, overlap, "range/chop discriminator"),
            Evidence("directional_persistence", 0.20, persistence, "trend discriminator"),
            Evidence("breakout_follow_through", 0.20, breakout_follow, "expansion discriminator"),
            Evidence("directional_efficiency", 0.10, directional_efficiency, "path efficiency stabilizer"),
            Evidence("price_action_confidence", 0.10, pa_confidence, "algorithmic price-action confidence"),
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
