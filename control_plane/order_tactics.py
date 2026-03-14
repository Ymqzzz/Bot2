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
        )
