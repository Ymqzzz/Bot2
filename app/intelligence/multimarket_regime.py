from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import Evidence


@dataclass(frozen=True)
class MultiMarketRegimeAssessment:
    trend_support_score: float
    risk_off_score: float
    usd_strength_score: float
    confidence: float
    regime_label: str
    rationale: list[Evidence]


class MultiMarketRegimeEngine:
    """Cross-market context model used to bias FX regime interpretation."""

    def compute(self, data: EngineInput) -> MultiMarketRegimeAssessment:
        ctx = data.context.get("multi_market") or data.context.get("cross_asset") or {}

        dxy_change = float(ctx.get("dxy_change", 0.0))
        us10y_change_bps = float(ctx.get("us10y_change_bps", ctx.get("rates_change", 0.0) * 100.0))
        spx_return = float(ctx.get("spx_return", 0.0))
        gold_return = float(ctx.get("gold_return", 0.0))
        crude_return = float(ctx.get("crude_return", 0.0))
        vix_change = float(ctx.get("vix_change", 0.0))

        abs_inputs = [abs(dxy_change), abs(us10y_change_bps) / 25.0, abs(spx_return), abs(gold_return), abs(crude_return), abs(vix_change)]
        confidence = clamp(sum(1.0 for x in abs_inputs if x > 0.0) / len(abs_inputs), 0.25, 1.0)

        # Normalize to [0,1] where 1 implies stronger risk-off / USD strength.
        usd_strength = clamp(0.5 + 8.0 * dxy_change + 0.012 * us10y_change_bps)
        risk_off = clamp(0.5 + 1.2 * max(-spx_return, 0.0) + 0.7 * max(vix_change, 0.0) + 0.4 * max(gold_return, 0.0))
        growth_impulse = clamp(0.5 + 0.9 * max(spx_return, 0.0) + 0.6 * max(crude_return, 0.0) - 0.4 * max(vix_change, 0.0))
        trend_support = clamp(0.55 * growth_impulse + 0.45 * (1.0 - risk_off))

        if risk_off > 0.67 and usd_strength > 0.58:
            regime_label = "macro_risk_off_usd_bid"
        elif trend_support > 0.62 and risk_off < 0.48:
            regime_label = "macro_risk_on_trend"
        elif usd_strength > 0.64:
            regime_label = "macro_usd_strength"
        elif usd_strength < 0.38:
            regime_label = "macro_usd_weakness"
        else:
            regime_label = "macro_balanced"

        rationale = [
            Evidence("dxy_change", 0.35, dxy_change, "broad USD direction proxy"),
            Evidence("us10y_change_bps", 0.20, us10y_change_bps, "rates differential pressure"),
            Evidence("spx_return", 0.20, spx_return, "risk appetite proxy"),
            Evidence("vix_change", 0.15, vix_change, "volatility sentiment proxy"),
            Evidence("gold_return", 0.10, gold_return, "defensive allocation proxy"),
        ]

        return MultiMarketRegimeAssessment(
            trend_support_score=trend_support,
            risk_off_score=risk_off,
            usd_strength_score=usd_strength,
            confidence=confidence,
            regime_label=regime_label,
            rationale=rationale,
        )
