from __future__ import annotations

from typing import Any

from .config import TradeIntelConfig
from .models import ExitPlan
from .reason_codes import *


class SmartExitEngine:
    def __init__(self, config: TradeIntelConfig):
        self.config = config

    def build_initial_exit_plan(self, open_trade_context: dict[str, Any]) -> ExitPlan:
        trade_id = str(open_trade_context["trade_id"])
        strategy = str(open_trade_context.get("setup_type", "")).lower()
        entry = float(open_trade_context["entry_price"])
        stop = float(open_trade_context["stop_loss"])
        risk = abs(entry - stop)
        side = 1 if str(open_trade_context.get("side", "BUY")).upper() == "BUY" else -1
        tp1 = entry + side * risk * 1.2
        tp2 = entry + side * risk * 2.0
        max_hold = self._max_hold(strategy)
        return ExitPlan(
            trade_id=trade_id,
            exit_plan_type=f"{strategy or 'generic'}_smart",
            initial_tp_levels=[tp1, tp2],
            initial_partial_schedule=[
                {"trigger_r": 1.2, "fraction": 0.35, "reason": "first_objective"},
                {"trigger_r": 2.0, "fraction": 0.30, "reason": "second_objective"},
            ],
            break_even_arming_rule=f"r>={self.config.BREAK_EVEN_ARM_R_MULTIPLE} and structure_confirmed",
            trailing_rule=f"arm at r>={self.config.TRAILING_ARM_R_MULTIPLE} then trail by atr_factor",
            time_stop_rule="exit if max_hold reached without thesis progress",
            regime_invalidation_rule="exit when regime_alignment_score<0.2",
            execution_invalidation_rule="exit when execution_risk_score>0.9 persists",
            max_hold_seconds=max_hold,
            reason_codes=[EXIT_AT_TARGET],
        )

    def evaluate_live_exit(self, open_trade_context: dict[str, Any], live_trade_state: dict[str, Any], market_intel_snapshot: dict[str, Any]) -> dict[str, Any]:
        if self.should_force_exit(open_trade_context, live_trade_state, market_intel_snapshot):
            return {"action": "force_exit", "reason_codes": [EXIT_REGIME_INVALIDATION, EXIT_EXECUTION_DISLOCATION]}
        if self.should_take_partial(open_trade_context, live_trade_state, market_intel_snapshot):
            return {"action": "take_partial", "reason_codes": [EXIT_PARTIAL_AT_PROFILE]}
        if self.should_arm_break_even(open_trade_context, live_trade_state, market_intel_snapshot):
            return {"action": "arm_break_even", "reason_codes": [EXIT_BREAK_EVEN_SAVE]}
        if self.should_trail(open_trade_context, live_trade_state, market_intel_snapshot):
            return {"action": "trail", "reason_codes": [EXIT_TRAILING_STOP]}
        return {"action": "hold", "reason_codes": []}

    def should_take_partial(self, open_trade_context: dict[str, Any], live_trade_state: dict[str, Any], market_intel_snapshot: dict[str, Any]) -> bool:
        if not self.config.ENABLE_PARTIALS:
            return False
        return float(live_trade_state.get("r_multiple", 0.0)) >= 1.2 and bool(market_intel_snapshot.get("near_profile_level", True))

    def should_arm_break_even(self, open_trade_context: dict[str, Any], live_trade_state: dict[str, Any], market_intel_snapshot: dict[str, Any]) -> bool:
        if not self.config.ENABLE_BREAK_EVEN_ARMING:
            return False
        return (
            float(live_trade_state.get("r_multiple", 0.0)) >= self.config.BREAK_EVEN_ARM_R_MULTIPLE
            and bool(live_trade_state.get("structure_confirmed", True))
            and float(market_intel_snapshot.get("execution_risk_score", 0.0)) < 0.8
        )

    def should_trail(self, open_trade_context: dict[str, Any], live_trade_state: dict[str, Any], market_intel_snapshot: dict[str, Any]) -> bool:
        return float(live_trade_state.get("r_multiple", 0.0)) >= self.config.TRAILING_ARM_R_MULTIPLE

    def should_force_exit(self, open_trade_context: dict[str, Any], live_trade_state: dict[str, Any], market_intel_snapshot: dict[str, Any]) -> bool:
        if self.config.ENABLE_TIME_STOPS and int(live_trade_state.get("seconds_held", 0)) > int(open_trade_context.get("max_hold_seconds") or self.config.DEFAULT_MAX_HOLD_SECONDS):
            if float(live_trade_state.get("r_multiple", 0.0)) < 0.25:
                return True
        if self.config.ENABLE_REGIME_INVALIDATION_EXITS and float(market_intel_snapshot.get("regime_alignment_score", 1.0)) < 0.2:
            return True
        if self.config.ENABLE_EXECUTION_DISLOCATION_EXITS and float(market_intel_snapshot.get("execution_risk_score", 0.0)) > 0.92:
            return True
        return False

    def _max_hold(self, strategy: str) -> int:
        if "breakout" in strategy:
            return self.config.BREAKOUT_MAX_HOLD_SECONDS
        if "mean" in strategy:
            return self.config.MEAN_REVERSION_MAX_HOLD_SECONDS
        if "sweep" in strategy:
            return self.config.SWEEP_REVERSAL_MAX_HOLD_SECONDS
        if "trend" in strategy:
            return self.config.TREND_PULLBACK_MAX_HOLD_SECONDS
        return self.config.DEFAULT_MAX_HOLD_SECONDS
