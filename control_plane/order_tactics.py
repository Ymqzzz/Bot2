from __future__ import annotations

from .config import ControlPlaneConfig
from .models import EventDecision, ExecutionDecision, OrderTacticPlan, RegimeDecision


class OrderTacticPlanner:
    def __init__(self, config: ControlPlaneConfig):
        self.config = config

    def build_tactic_plan(self, candidate: dict, execution_decision: ExecutionDecision, regime_decision: RegimeDecision, event_decision: EventDecision) -> OrderTacticPlan:
        tactic = execution_decision.recommended_tactic
        strategy = candidate.get("strategy_name", "")
        reason_codes = list(execution_decision.reason_codes)
        fallback = self.config.TACTIC_FALLBACK_TO_MARKET_ALLOWED and tactic in {"stop_entry", "aggressive_limit"}
        num_clips = min(self.config.TACTIC_MAX_CLIPS, 2 if self.config.TACTIC_ALLOW_STAGING else 1)
        schedule = [i * self.config.TACTIC_MIN_CLIP_SECONDS for i in range(num_clips)]

        if "MeanReversion" in strategy and regime_decision.regime_name == "rotation_mean_reversion":
            tactic = "passive_limit"
            fallback = False
        if regime_decision.regime_name == "event_chaos":
            num_clips = 1
            schedule = [0]
            fallback = False

        return OrderTacticPlan(
            candidate_id=candidate["candidate_id"],
            instrument=candidate["instrument"],
            tactic_type=tactic,
            entry_style="confirm_then_enter" if tactic in {"stop_entry", "market_immediate"} else "pullback_or_revert",
            entry_price=candidate.get("entry_price"),
            limit_offset_bps=1.5 if tactic in {"passive_limit", "aggressive_limit"} else None,
            stop_offset_bps=1.2 if tactic in {"stop_entry", "stop_then_fallback_market"} else None,
            aggression_level="high" if tactic in {"market_immediate", "stop_entry"} else "medium",
            staging_enabled=num_clips > 1,
            num_clips=num_clips,
            clip_schedule_seconds=schedule,
            cancel_after_seconds=execution_decision.cancel_if_not_filled_seconds,
            fallback_to_market=fallback,
            fallback_conditions=["spread_normalized", "fill_timeout"] if fallback else [],
            reason_codes=reason_codes,
from .models import OrderTacticPlan


class OrderTacticPlanner:
    def __init__(self, config: ControlPlaneConfig | None = None) -> None:
        self.config = config or ControlPlaneConfig()

    def build_tactic_plan(self, candidate, execution_decision, regime_decision, event_decision) -> OrderTacticPlan:
        tactic = execution_decision.recommended_tactic
        entry_style = "confirm"
        limit_offset = None
        stop_offset = None
        fallback_conditions = []
        if candidate.strategy_name == "Breakout-Squeeze" and regime_decision.regime_name == "trend_expansion":
            tactic = "stop_then_fallback_market" if event_decision.spread_normalized else "stop_entry"
            stop_offset = 3.0
            fallback_conditions = ["breakout_continues", "spread_within_limit"]
        elif candidate.strategy_name == "Range-MeanReversion":
            tactic = "passive_limit"
            limit_offset = -1.5
            entry_style = "fade"
            fallback_conditions = ["cancel_if_rotation_breaks"]
        elif candidate.strategy_name == "Liquidity-Draw/Sweep":
            tactic = "aggressive_limit"
            limit_offset = -0.5
            fallback_conditions = ["cancel_if_reclaim_fails"]
        staging = self.config.TACTIC_ALLOW_STAGING and tactic in {"staged_market", "staged_limit", "stop_then_fallback_market"}
        clips = min(self.config.TACTIC_MAX_CLIPS, 2 if staging else 1)
        schedule = [i * self.config.TACTIC_MIN_CLIP_SECONDS for i in range(clips)]
        return OrderTacticPlan(
            candidate_id=candidate.candidate_id,
            instrument=candidate.instrument,
            tactic_type=tactic,
            entry_style=entry_style,
            entry_price=None,
            limit_offset_bps=limit_offset,
            stop_offset_bps=stop_offset,
            aggression_level="high" if "market" in tactic or "stop" in tactic else "low",
            staging_enabled=staging,
            num_clips=clips,
            clip_schedule_seconds=schedule,
            cancel_after_seconds=execution_decision.cancel_if_not_filled_seconds,
            fallback_to_market=self.config.TACTIC_FALLBACK_TO_MARKET_ALLOWED and "fallback" in tactic,
            fallback_conditions=fallback_conditions,
            reason_codes=execution_decision.reason_codes,
        )
