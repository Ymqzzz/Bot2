from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .config import ControlPlaneConfig, RegimeUncertainBehavior
from .models import EventDecision, RegimeDecision
from .reason_codes import (
    REGIME_BREAKOUT_ALLOWED,
    REGIME_BREAKOUT_SUPPRESSED,
    REGIME_DEAD_ZONE,
    REGIME_EVENT_CHAOS,
    REGIME_MEAN_REVERSION_ALLOWED,
    REGIME_MEAN_REVERSION_BLOCKED,
    REGIME_PULLBACK_ALLOWED,
    REGIME_PULLBACK_SUPPRESSED,
    REGIME_ROTATION,
    REGIME_TREND_EXPANSION,
    REGIME_UNCERTAIN,
)


class RegimeEngine:
    def __init__(self, config: ControlPlaneConfig | None = None) -> None:
        self.config = config or ControlPlaneConfig()

    def classify_instrument_regime(
        self,
        instrument: str,
        snapshot: dict | None,
        bars: pd.DataFrame | None,
        event_decision: EventDecision,
    ) -> RegimeDecision:
        snapshot = snapshot or {}
        bars = bars if bars is not None else pd.DataFrame()
        asof = datetime.now(timezone.utc)

        close = bars.get("close") if not bars.empty and "close" in bars else pd.Series([1.0, 1.0])
        trend_strength = float(abs(close.iloc[-1] - close.iloc[max(0, len(close) - 20)]) / max(1e-8, abs(close.iloc[-1])))
        spread_shock = float(snapshot.get("spread_shock", snapshot.get("spread_dislocation", 0.0)) or 0.0)
        rotation = float(snapshot.get("rotation", 0.0) or 0.0)
        compression = float(snapshot.get("compression", 0.0) or 0.0)
        expansion = float(snapshot.get("velocity", 0.0) or 0.0)
        event_chaos = max(spread_shock, 1.0 - event_decision.event_risk_multiplier)
        dead_zone = 1.0 if trend_strength < 0.0005 and expansion < 0.2 else 0.0

        regime_name = "uncertain_mixed"
        reason_codes = [REGIME_UNCERTAIN]
        confidence = max(0.0, min(1.0, trend_strength * 20))
        if trend_strength >= self.config.TREND_STRENGTH_THRESHOLD or expansion >= self.config.EXPANSION_THRESHOLD:
            regime_name = "trend_expansion"
            reason_codes = [REGIME_TREND_EXPANSION]
            confidence = max(confidence, 0.7)
        elif rotation >= self.config.ROTATION_THRESHOLD:
            regime_name = "rotation_mean_reversion"
            reason_codes = [REGIME_ROTATION]
            confidence = max(confidence, 0.6)
        elif dead_zone > 0:
            regime_name = "dead_zone"
            reason_codes = [REGIME_DEAD_ZONE]
            confidence = 0.4

        if event_chaos >= self.config.EVENT_CHAOS_THRESHOLD:
            regime_name = "uncertain_mixed"
            reason_codes = [REGIME_EVENT_CHAOS, REGIME_UNCERTAIN]
            confidence = min(confidence, 0.5)

        allowed = ["Trend-Pullback", "Breakout-Squeeze", "Squeeze-Breakout", "Range-MeanReversion", "Liquidity-Sweep-Reversal"]
        blocked: list[str] = []
        suppressed: list[str] = []
        if not event_decision.allow_breakout:
            suppressed.extend(["Breakout-Squeeze", "Squeeze-Breakout"])
            reason_codes.append(REGIME_BREAKOUT_SUPPRESSED)
        else:
            reason_codes.append(REGIME_BREAKOUT_ALLOWED)
        if not event_decision.allow_mean_reversion:
            blocked.append("Range-MeanReversion")
            reason_codes.append(REGIME_MEAN_REVERSION_BLOCKED)
        else:
            reason_codes.append(REGIME_MEAN_REVERSION_ALLOWED)
        if not event_decision.allow_trend_pullback:
            suppressed.append("Trend-Pullback")
            reason_codes.append(REGIME_PULLBACK_SUPPRESSED)
        else:
            reason_codes.append(REGIME_PULLBACK_ALLOWED)

        if confidence < self.config.REGIME_MIN_CONFIDENCE:
            if self.config.REGIME_UNCERTAIN_BEHAVIOR == RegimeUncertainBehavior.BLOCK:
                blocked.extend(allowed)
            elif self.config.REGIME_UNCERTAIN_BEHAVIOR == RegimeUncertainBehavior.RESTRICT:
                suppressed.extend(["Breakout-Squeeze", "Squeeze-Breakout"])

        multipliers = {s: 1.0 for s in allowed}
        for s in suppressed:
            multipliers[s] = 0.5
        for s in blocked:
            multipliers[s] = 0.0

        return RegimeDecision(
            instrument=instrument,
            asof=asof,
            regime_name=regime_name,
            regime_confidence=max(0.0, min(1.0, confidence)),
            regime_state_label=regime_name,
            trend_strength_score=max(0.0, min(1.0, trend_strength)),
            rotation_score=max(0.0, min(1.0, rotation)),
            compression_score=max(0.0, min(1.0, compression)),
            expansion_score=max(0.0, min(1.0, expansion)),
            event_chaos_score=max(0.0, min(1.0, event_chaos)),
            dead_zone_score=dead_zone,
            allowed_strategies=allowed,
            suppressed_strategies=sorted(set(suppressed)),
            blocked_strategies=sorted(set(blocked)),
            strategy_weight_multipliers=multipliers,
            sizing_cap_multiplier=1.0,
            order_preference="balanced",
            exit_posture="normal",
            reason_codes=list(dict.fromkeys(reason_codes)),
        )
