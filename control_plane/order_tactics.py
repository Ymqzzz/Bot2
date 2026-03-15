from __future__ import annotations

from .config import ControlPlaneConfig
from .models import EventDecision, ExecutionDecision, OrderTacticPlan, RegimeDecision


class OrderTacticPlanner:
    def __init__(self, config: ControlPlaneConfig | None = None) -> None:
        self.config = config or ControlPlaneConfig()

    def build_tactic_plan(self, candidate, execution_decision: ExecutionDecision, regime_decision: RegimeDecision, event_decision: EventDecision) -> OrderTacticPlan:
        candidate_id = getattr(candidate, "candidate_id", candidate.get("candidate_id"))
        instrument = getattr(candidate, "instrument", candidate.get("instrument"))

        tactic = execution_decision.recommended_tactic
        entry_style = "market"
        limit_offset = None
        stop_offset = None
        aggression = "medium"
        if tactic == "passive_limit":
            entry_style = "limit"
            limit_offset = 0.5
            aggression = "low"
        elif tactic == "stop_entry":
            entry_style = "stop"
            stop_offset = 0.8
            aggression = "high"

        num_clips = max(1, self.config.TACTIC_MAX_CLIPS)
        schedule = [self.config.TACTIC_MIN_CLIP_SECONDS * i for i in range(num_clips)]

        return OrderTacticPlan(
            candidate_id=candidate_id,
            instrument=instrument,
            tactic_type=tactic,
            entry_style=entry_style,
            entry_price=None,
            limit_offset_bps=limit_offset,
            stop_offset_bps=stop_offset,
            aggression_level=aggression,
            staging_enabled=self.config.TACTIC_ALLOW_STAGING,
            num_clips=num_clips,
            clip_schedule_seconds=schedule,
            cancel_after_seconds=self.config.EXECUTION_DEFAULT_CANCEL_AFTER_SECONDS,
            fallback_to_market=self.config.TACTIC_FALLBACK_TO_MARKET_ALLOWED,
            fallback_conditions=["timeout", "slippage_spike"],
            reason_codes=[],
        )
