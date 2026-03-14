from __future__ import annotations

from .config import ControlPlaneConfig
from .models import EventDecision, ExecutionDecision, RegimeDecision
from .reason_codes import *


class ExecutionIntelligenceEngine:
    def __init__(self, config: ControlPlaneConfig):
        self.config = config

    def estimate_fill_probability(self, candidate: dict, tactic: str, microstructure_snapshot: dict) -> float:
        liq = float(microstructure_snapshot.get("liq_factor", 0.5))
        spread = float(microstructure_snapshot.get("spread_pctile", 50.0)) / 100.0
        tactic_bonus = {"passive_limit": -0.15, "aggressive_limit": 0.0, "stop_entry": -0.05, "market_immediate": 0.1}.get(tactic, 0.0)
        return max(0.0, min(1.0, 0.75 + tactic_bonus + (liq - 0.5) * 0.4 - spread * 0.35))

    def estimate_expected_slippage(self, candidate: dict, tactic: str, execution_quality_snapshot: dict) -> float:
        spread = float(execution_quality_snapshot.get("spread_bps", 1.5))
        vel = float(execution_quality_snapshot.get("velocity", 0.5))
        mult = {"passive_limit": 0.5, "aggressive_limit": 0.8, "stop_entry": 1.1, "market_immediate": 1.2}.get(tactic, 1.0)
        return max(0.0, spread * mult * (1.0 + vel * 0.4))

    def estimate_late_entry_risk(self, candidate: dict, microstructure_snapshot: dict, regime_decision: RegimeDecision) -> float:
        impulse = float(microstructure_snapshot.get("impulse", 0.5))
        dist = float(microstructure_snapshot.get("distance_from_trigger_atr", 0.0))
        return max(0.0, min(1.0, impulse * 0.6 + dist * 0.4 + (0.1 if regime_decision.regime_name == "trend_expansion" else 0.0)))

    def estimate_escape_risk(self, candidate: dict, microstructure_snapshot: dict) -> float:
        return max(0.0, min(1.0, float(microstructure_snapshot.get("escape_velocity", 0.5))))

    def evaluate_entry(self, candidate: dict, market_intel_snapshot: dict, regime_decision: RegimeDecision, event_decision: EventDecision, recent_execution_stats: dict) -> ExecutionDecision:
        strategy = candidate.get("strategy_name", "")
        if "Breakout" in strategy:
            tactic = "stop_entry"
        elif "MeanReversion" in strategy:
            tactic = "passive_limit"
        else:
            tactic = "aggressive_limit"
        reason_codes = [EXEC_TACTIC_STOP if tactic == "stop_entry" else EXEC_TACTIC_LIMIT]

        fill = self.estimate_fill_probability(candidate, tactic, market_intel_snapshot)
        slip = self.estimate_expected_slippage(candidate, tactic, market_intel_snapshot)
        late = self.estimate_late_entry_risk(candidate, market_intel_snapshot, regime_decision)
        escape = self.estimate_escape_risk(candidate, market_intel_snapshot)
        spread_dislocation = float(market_intel_snapshot.get("spread_dislocation", 0.0))
        adverse = max(0.0, min(1.0, (slip / 10.0) + spread_dislocation * 0.4))

        allow = True
        if fill < self.config.EXECUTION_FILL_PROB_THRESHOLD:
            allow = False
            reason_codes.append(EXEC_TACTIC_FILL_PROB_LOW)
        if slip > self.config.EXECUTION_MAX_EXPECTED_SLIPPAGE_BPS:
            allow = False
            reason_codes.append(EXEC_TACTIC_SLIPPAGE_HIGH)
        if late > self.config.EXECUTION_MAX_LATE_ENTRY_RISK:
            allow = False
            reason_codes.append(EXEC_TACTIC_BLOCK_LATE_ENTRY)
        if spread_dislocation > 0.8:
            allow = False
            reason_codes.append(EXEC_TACTIC_BLOCK_SPREAD_DISLOCATION)
        if escape > self.config.EXECUTION_MAX_ESCAPE_RISK:
            reason_codes.append(EXEC_TACTIC_ESCAPE_RISK_HIGH)

        if self.config.EXECUTION_REPRICE_ENABLED:
            reason_codes.append(EXEC_TACTIC_REPRICE_ENABLED)
            reason_codes.append(EXEC_TACTIC_RETRY_ENABLED)

        return ExecutionDecision(
            trade_id=candidate.get("candidate_id"),
            instrument=candidate.get("instrument", ""),
            recommended_tactic=tactic,
            secondary_tactic="market_immediate" if tactic in {"stop_entry", "aggressive_limit"} else None,
            allow_entry=allow and event_decision.execution_penalty_multiplier < 1.9,
            fill_probability_score=fill,
            expected_slippage_bps=slip * event_decision.execution_penalty_multiplier,
            adverse_selection_risk=adverse,
            late_entry_risk=late,
            spread_dislocation_risk=spread_dislocation,
            escape_risk_score=escape,
            reprice_allowed=self.config.EXECUTION_REPRICE_ENABLED,
            retry_allowed=True,
            max_retries=self.config.EXECUTION_DEFAULT_MAX_RETRIES,
            cancel_if_not_filled_seconds=self.config.EXECUTION_DEFAULT_CANCEL_AFTER_SECONDS,
            reason_codes=reason_codes,
        )
