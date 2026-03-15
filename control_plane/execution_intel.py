from __future__ import annotations

from .config import ControlPlaneConfig
from .models import EventDecision, ExecutionDecision, RegimeDecision
from .reason_codes import (
    EXEC_TACTIC_AGGRESSIVE_STOP,
    EXEC_TACTIC_BLOCK_LATE_ENTRY,
    EXEC_TACTIC_BLOCK_SPREAD_DISLOCATION,
    EXEC_TACTIC_FILL_PROB_LOW,
    EXEC_TACTIC_MARKET,
    EXEC_TACTIC_PASSIVE_LIMIT,
    EXEC_TACTIC_REPRICE_ENABLED,
    EXEC_TACTIC_RETRY_ENABLED,
    EXEC_TACTIC_SLIPPAGE_HIGH,
)


class ExecutionIntelligenceEngine:
    def __init__(self, config: ControlPlaneConfig | None = None) -> None:
        self.config = config or ControlPlaneConfig()

    def evaluate_entry(self, candidate, market_intel: dict, regime_decision: RegimeDecision, event_decision: EventDecision, context: dict) -> ExecutionDecision:
        spread_dislocation = float(market_intel.get("spread_dislocation", 0.0) or 0.0)
        spread_bps = float(market_intel.get("spread_bps", 0.0) or 0.0)
        impulse = float(market_intel.get("impulse", market_intel.get("velocity", 0.0)) or 0.0)
        dist = float(market_intel.get("distance_from_trigger_atr", 0.0) or 0.0)
        escape = float(market_intel.get("escape_velocity", 0.0) or 0.0)

        late_entry_risk = min(1.0, max(0.0, dist))
        slippage = spread_bps * (1.0 + spread_dislocation)
        fill_prob = max(0.0, min(1.0, 1.0 - spread_dislocation - 0.2 * max(0.0, dist - 0.25)))

        allow = True
        reasons: list[str] = []
        if late_entry_risk > self.config.EXECUTION_MAX_LATE_ENTRY_RISK:
            allow = False
            reasons.append(EXEC_TACTIC_BLOCK_LATE_ENTRY)
        if spread_dislocation >= 0.8:
            allow = False
            reasons.append(EXEC_TACTIC_BLOCK_SPREAD_DISLOCATION)
        if fill_prob < self.config.EXECUTION_FILL_PROB_THRESHOLD:
            reasons.append(EXEC_TACTIC_FILL_PROB_LOW)
        if slippage > self.config.EXECUTION_MAX_EXPECTED_SLIPPAGE_BPS:
            reasons.append(EXEC_TACTIC_SLIPPAGE_HIGH)

        tactic = "market_immediate"
        if regime_decision.regime_name == "rotation_mean_reversion":
            tactic = "passive_limit"
            reasons.append(EXEC_TACTIC_PASSIVE_LIMIT)
        elif impulse > 0.8:
            tactic = "stop_entry"
            reasons.append(EXEC_TACTIC_AGGRESSIVE_STOP)
        else:
            reasons.append(EXEC_TACTIC_MARKET)

        if self.config.EXECUTION_REPRICE_ENABLED:
            reasons.append(EXEC_TACTIC_REPRICE_ENABLED)
        reasons.append(EXEC_TACTIC_RETRY_ENABLED)

        return ExecutionDecision(
            trade_id=None,
            instrument=getattr(candidate, "instrument", candidate.get("instrument")),
            recommended_tactic=tactic,
            secondary_tactic="market_immediate",
            allow_entry=allow,
            fill_probability_score=fill_prob,
            expected_slippage_bps=slippage,
            adverse_selection_risk=spread_dislocation,
            late_entry_risk=late_entry_risk,
            spread_dislocation_risk=spread_dislocation,
            escape_risk_score=escape,
            reprice_allowed=self.config.EXECUTION_REPRICE_ENABLED,
            retry_allowed=True,
            max_retries=self.config.EXECUTION_DEFAULT_MAX_RETRIES,
            cancel_if_not_filled_seconds=self.config.EXECUTION_DEFAULT_CANCEL_AFTER_SECONDS,
            reason_codes=list(dict.fromkeys(reasons)),
        )
