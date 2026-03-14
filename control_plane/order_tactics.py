from __future__ import annotations

from .config import ControlPlaneConfig
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
