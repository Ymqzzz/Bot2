from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import CrossAssetContextState, Evidence, Direction, MultiTimeframeBiasState


class CrossAssetEngine:
    def compute(self, data: EngineInput, mtf: MultiTimeframeBiasState) -> CrossAssetContextState:
        ctx = data.context.get("cross_asset", {})
        dxy = ctx.get("dxy_change")
        rates = ctx.get("rates_change")
        risk = ctx.get("risk_on")
        if dxy is None and rates is None and risk is None:
            return CrossAssetContextState(
                timestamp=data.timestamp,
                instrument=data.instrument,
                trace_id=data.trace_id,
                confidence=0.2,
                confirmation_label="missing",
                rationale=[Evidence("feeds", 1.0, 0.0, "cross-asset feeds unavailable")],
            )
        usd_alignment = clamp(0.5 + (-float(dxy or 0.0) * 5.0), -1.0, 1.0)
        macro_support = clamp(0.5 + 0.3 * float(rates or 0.0) + 0.2 * float(risk or 0.0))
        risk_sentiment = clamp(0.5 + 0.5 * float(risk or 0.0))
        local_dir = 1.0 if mtf.htf_bias == Direction.BULLISH else -1.0 if mtf.htf_bias == Direction.BEARISH else 0.0
        divergence = clamp(abs((usd_alignment - 0.5) - local_dir * 0.5) + (1.0 - macro_support) * 0.3)
        label = "confirming" if divergence < 0.35 else "contradicting" if divergence > 0.65 else "mixed"
        return CrossAssetContextState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=0.7,
            sources=["cross_asset"],
            rationale=[
                Evidence("usd_alignment", 0.4, usd_alignment, "usd proxy context"),
                Evidence("macro_support", 0.35, macro_support, "rates+risk support"),
                Evidence("divergence", 0.25, divergence, "context vs local setup"),
            ],
            usd_alignment_score=usd_alignment,
            macro_support_score=macro_support,
            risk_sentiment_score=risk_sentiment,
            divergence_score=divergence,
            confirmation_label=label,
        )
