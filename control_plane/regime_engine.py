from __future__ import annotations

from datetime import datetime, timezone

from .config import ControlPlaneConfig, RegimeUncertainBehavior
from .models import RegimeDecision
from .reason_codes import *
from .regime_features import extract_regime_features
from .regime_policies import REGIME_POLICY_TABLE


class RegimeEngine:
    def __init__(self, config: ControlPlaneConfig | None = None) -> None:
        self.config = config or ControlPlaneConfig()

    def classify_instrument_regime(self, instrument, market_intel_snapshot, recent_bars, event_decision) -> RegimeDecision:
        f = extract_regime_features(recent_bars, market_intel_snapshot)
        scores = {
            "trend_expansion": 0.45 * f["trend_strength_score"] + 0.35 * f["expansion_score"] + 0.20 * f["intraday_impulse_quality_score"],
            "rotation_mean_reversion": 0.5 * f["rotation_score"] + 0.25 * f["value_area_rotation_score"] + 0.25 * f["structure_rejection_density"],
            "compression_pre_breakout": 0.60 * f["compression_score"] + 0.40 * f["realized_vol_expansion_factor"],
            "sweep_reversal": 0.65 * f["sweep_tendency_score"] + 0.35 * f["structure_rejection_density"],
            "event_chaos": max(f["event_chaos_score"], 1.0 if event_decision.event_phase in {"release_window", "headline_risk"} else 0.0),
            "dead_zone": f["dead_zone_score"],
        }
        regime_name = max(scores, key=scores.get)
        confidence = float(scores[regime_name])
        if confidence < self.config.REGIME_MIN_CONFIDENCE:
            regime_name = "uncertain_mixed"
        if event_decision.event_state in {"release_active", "headline_risk"}:
            regime_name = "event_chaos"
        policy = REGIME_POLICY_TABLE[regime_name]
        reasons = [
            REGIME_EVENT_CHAOS if regime_name == "event_chaos" else "",
            REGIME_DEAD_ZONE if regime_name == "dead_zone" else "",
            REGIME_UNCERTAIN if regime_name == "uncertain_mixed" else "",
        ]
        if "Breakout-Squeeze" in policy["allowed"]:
            reasons.append(REGIME_BREAKOUT_ALLOWED)
        if "Range-MeanReversion" in policy["allowed"]:
            reasons.append(REGIME_MEAN_REVERSION_ALLOWED)
        elif "Range-MeanReversion" in policy["blocked"]:
            reasons.append(REGIME_MEAN_REVERSION_BLOCKED)
        if "Trend-Pullback" in policy["allowed"]:
            reasons.append(REGIME_PULLBACK_ALLOWED)
        if "Trend-Pullback" in policy["suppressed"]:
            reasons.append(REGIME_PULLBACK_SUPPRESSED)
        if regime_name == "uncertain_mixed" and self.config.REGIME_UNCERTAIN_BEHAVIOR == RegimeUncertainBehavior.block:
            policy = {**policy, "blocked": ["Breakout-Squeeze", "Range-MeanReversion", "Liquidity-Draw/Sweep", "Trend-Pullback"]}

        return RegimeDecision(
            instrument=instrument,
            asof=datetime.now(timezone.utc),
            regime_name=regime_name,
            regime_confidence=confidence,
            regime_state_label=regime_name,
            trend_strength_score=f["trend_strength_score"],
            rotation_score=f["rotation_score"],
            compression_score=f["compression_score"],
            expansion_score=f["expansion_score"],
            event_chaos_score=f["event_chaos_score"],
            dead_zone_score=f["dead_zone_score"],
            allowed_strategies=policy["allowed"],
            suppressed_strategies=policy["suppressed"],
            blocked_strategies=policy["blocked"],
            strategy_weight_multipliers=policy["suppression_multipliers"],
            sizing_cap_multiplier=policy["sizing_cap"],
            order_preference=policy["order_preference"],
            exit_posture=policy["exit_posture"],
            reason_codes=[r for r in reasons if r],
        )

    def classify_global_regime(self, regime_decisions) -> dict:
        names = [d.regime_name for d in regime_decisions.values()]
        if not names:
            return {"global_regime": "uncertain_mixed", "dispersion": 0.0}
        mode = max(set(names), key=names.count)
        return {"global_regime": mode, "dispersion": 1.0 - names.count(mode) / len(names)}

    def get_strategy_policy(self, regime_decision: RegimeDecision) -> dict:
        return REGIME_POLICY_TABLE.get(regime_decision.regime_name, REGIME_POLICY_TABLE["uncertain_mixed"])
