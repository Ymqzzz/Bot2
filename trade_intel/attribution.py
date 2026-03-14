from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .classifiers import (
    classify_entry_quality,
    classify_environment_bucket,
    classify_exit_quality,
    classify_setup_bucket,
    classify_trade_outcome,
)
from .config import TradeIntelConfig
from .models import (
    EntryQualityAssessment,
    ExitQualityAssessment,
    TradeFingerprint,
    TradeLifecycleRecord,
    TradeOutcomeAttribution,
    TradePathMetrics,
)


class TradeAttributionEngine:
    def __init__(self, config: TradeIntelConfig):
        self.config = config

    def build_trade_fingerprint(self, candidate: dict[str, Any], market_context: dict[str, Any], sizing_reason_codes: list[str], approval_reason_codes: list[str]) -> TradeFingerprint:
        now = datetime.now(timezone.utc)
        return TradeFingerprint(
            trade_id=str(candidate.get("trade_id") or f"{candidate.get('instrument','NA')}-{int(now.timestamp())}"),
            instrument=str(candidate.get("instrument", "")),
            strategy_name=str(candidate.get("strategy_name", candidate.get("strategy", ""))),
            setup_type=str(candidate.get("setup_type", candidate.get("strategy_name", "generic"))),
            subtype=candidate.get("subtype"),
            decision_ts=now,
            entry_ts=None,
            side=str(candidate.get("side", "BUY")),
            entry_planned=float(candidate.get("entry_price", 0.0)),
            entry_filled=None,
            stop_initial=float(candidate.get("stop_loss", 0.0)),
            target_initial=float(candidate.get("take_profit", 0.0)),
            order_type=str(candidate.get("order_type", "MARKET")),
            confidence_raw=float(candidate.get("confidence", 0.5)),
            expected_value_raw=float(candidate.get("expected_value_proxy", candidate.get("ev_r", 0.0))),
            rr_planned=float(candidate.get("rr", 0.0)),
            intel_quality_score=float(candidate.get("intel_quality_score", 0.5)),
            entry_precision_score=float(candidate.get("entry_precision_score", 0.5)),
            execution_feasibility_score=float(candidate.get("execution_feasibility_score", 0.5)),
            liquidity_event_risk_score=float(market_context.get("event_risk_score", 0.0)),
            market_state_quality_score=float(market_context.get("market_state_quality_score", 0.5)),
            session_name=str(market_context.get("session_name", "unknown")),
            regime_name=str(market_context.get("regime_name", market_context.get("mode", "unknown"))),
            spread_regime=str(market_context.get("spread_regime", "normal")),
            gamma_mode=market_context.get("gamma_mode"),
            volume_profile_state=market_context.get("volume_profile_state"),
            cross_asset_state=market_context.get("cross_asset_state"),
            sizing_reason_codes=sizing_reason_codes,
            approval_reason_codes=approval_reason_codes,
            snapshot_ref=market_context.get("snapshot_ref"),
        )

    def assess_entry_quality(self, planned_entry: float, filled_entry: float, side: str, market_context: dict[str, Any]) -> EntryQualityAssessment:
        side_sign = 1 if side.upper() == "BUY" else -1
        slip_bps = abs((filled_entry - planned_entry) / max(planned_entry, 1e-9)) * 10000
        move_spent = float(market_context.get("move_spent_fraction", 0.0))
        label, score, reasons = classify_entry_quality(
            slippage_bps=slip_bps,
            spread_bps=float(market_context.get("spread_bps", 1.5)),
            distance_struct_bps=float(market_context.get("distance_struct_bps", 8.0)),
            distance_profile_bps=float(market_context.get("distance_profile_bps", 8.0)),
            move_spent_fraction=move_spent,
            adverse_selection_score=float(market_context.get("adverse_selection_score", 0.0)),
            passive_improvement=(filled_entry - planned_entry) * side_sign < 0,
        )
        return EntryQualityAssessment(
            entry_quality_label=label,
            entry_quality_score=score,
            was_late=move_spent > 0.7,
            was_early=float(market_context.get("entered_before_confirmation", 0.0)) > 0.5,
            was_chased=slip_bps > 4,
            was_passive_improvement=(filled_entry - planned_entry) * side_sign < 0,
            filled_near_optimal_zone=float(market_context.get("distance_struct_bps", 8.0)) <= 6,
            distance_from_structural_level_bps=float(market_context.get("distance_struct_bps", 0.0)),
            distance_from_profile_level_bps=float(market_context.get("distance_profile_bps", 0.0)),
            slippage_bps=slip_bps,
            spread_at_entry_bps=float(market_context.get("spread_bps", 0.0)),
            adverse_selection_score=float(market_context.get("adverse_selection_score", 0.0)),
            entry_reason_codes=reasons,
        )

    def compute_path_metrics(self, trade_id: str, risk_per_unit: float, bars_held: int, seconds_held: int, pnl_path: list[float], spread_scores: list[float], vol_scores: list[float]) -> TradePathMetrics:
        mfe = max(pnl_path) if pnl_path else 0.0
        mae = min(pnl_path) if pnl_path else 0.0
        return TradePathMetrics(
            trade_id=trade_id,
            bars_held=bars_held,
            seconds_held=seconds_held,
            mfe_pips=mfe,
            mae_pips=mae,
            mfe_r=mfe / max(risk_per_unit, 1e-9),
            mae_r=mae / max(risk_per_unit, 1e-9),
            peak_unrealized_pnl=mfe,
            worst_unrealized_pnl=mae,
            time_to_mfe_sec=0 if pnl_path else None,
            time_to_mae_sec=0 if pnl_path else None,
            time_to_first_positive_sec=0 if any(x > 0 for x in pnl_path) else None,
            time_to_first_negative_sec=0 if any(x < 0 for x in pnl_path) else None,
            max_heat_fraction=abs(min(0.0, mae)) / max(abs(risk_per_unit), 1e-9),
            volatility_during_hold_score=sum(vol_scores) / max(len(vol_scores), 1),
            spread_during_hold_score=sum(spread_scores) / max(len(spread_scores), 1),
            execution_stress_during_hold_score=(sum(spread_scores) + sum(vol_scores)) / max(len(spread_scores) + len(vol_scores), 1),
        )

    def assess_exit_quality(self, path: TradePathMetrics, exit_context: dict[str, Any]) -> ExitQualityAssessment:
        mfe = max(path.mfe_r, 1e-9)
        captured = float(exit_context.get("realized_r", 0.0)) / mfe
        gaveback = max(0.0, (path.mfe_r - float(exit_context.get("realized_r", 0.0))) / mfe)
        label, score, reasons = classify_exit_quality(
            captured_mfe_fraction=captured,
            gaveback_fraction=gaveback,
            exit_at_structure=bool(exit_context.get("exit_at_structure", False)),
            exit_at_profile=bool(exit_context.get("exit_at_profile", False)),
            due_to_time_stop=bool(exit_context.get("due_to_time_stop", False)),
            due_to_trailing=bool(exit_context.get("due_to_trailing", False)),
            due_to_execution_dislocation=bool(exit_context.get("due_to_execution_dislocation", False)),
        )
        return ExitQualityAssessment(
            exit_quality_label=label,
            exit_quality_score=score,
            exit_reason_primary=reasons[0] if reasons else "none",
            exit_reason_secondary=reasons[1] if len(reasons) > 1 else None,
            exit_at_structure=bool(exit_context.get("exit_at_structure", False)),
            exit_at_profile_level=bool(exit_context.get("exit_at_profile", False)),
            exit_due_to_time_stop=bool(exit_context.get("due_to_time_stop", False)),
            exit_due_to_trailing=bool(exit_context.get("due_to_trailing", False)),
            exit_due_to_regime_change=bool(exit_context.get("due_to_regime_change", False)),
            exit_due_to_execution_dislocation=bool(exit_context.get("due_to_execution_dislocation", False)),
            captured_mfe_fraction=captured,
            gave_back_from_peak_fraction=gaveback,
            exit_reason_codes=reasons,
        )

    def attribute_outcome(self, trade_id: str, fingerprint: TradeFingerprint, entry_q: EntryQualityAssessment, exit_q: ExitQualityAssessment, path: TradePathMetrics, realized_r: float, market_context: dict[str, Any]) -> TradeOutcomeAttribution:
        fast = path.seconds_held <= self.config.FAST_INVALIDATION_SECONDS and path.mfe_r < 0.2 and realized_r < 0
        exec_drag = (entry_q.slippage_bps or 0.0) >= self.config.EXECUTION_LOSS_SLIPPAGE_THRESHOLD_BPS or exit_q.exit_due_to_execution_dislocation
        timing = entry_q.was_late or (entry_q.was_early and path.mae_r <= -self.config.TIMING_LOSS_MAE_THRESHOLD_R)
        regime = bool(market_context.get("regime_mismatch", False))
        exit_mis = bool((exit_q.gave_back_from_peak_fraction or 0.0) > self.config.MFE_GIVEBACK_HIGH_THRESHOLD and realized_r <= 0)
        label, score, driver, reasons = classify_trade_outcome(
            realized_r=realized_r,
            entry_quality_score=entry_q.entry_quality_score,
            exit_quality_score=exit_q.exit_quality_score,
            fast_invalidated=fast,
            execution_drag=exec_drag,
            timing_loss=timing,
            regime_mismatch=regime,
            exit_mismanaged=exit_mis,
        )
        env = classify_environment_bucket(
            fingerprint.regime_name,
            fingerprint.session_name,
            fingerprint.spread_regime,
            str(market_context.get("event_state", "normal")),
            str(market_context.get("execution_regime", "normal")),
        )
        setup = classify_setup_bucket(
            fingerprint.strategy_name,
            fingerprint.subtype,
            str(market_context.get("structure_context", "na")),
            str(market_context.get("profile_context", "na")),
            str(market_context.get("trigger_family", "na")),
        )
        return TradeOutcomeAttribution(
            trade_id=trade_id,
            outcome_label=label,
            outcome_score=score,
            driver_primary=driver,
            driver_secondary=reasons[0] if reasons else None,
            contributing_factors=reasons,
            failure_factors=[r for r in reasons if realized_r <= 0],
            success_factors=[r for r in reasons if realized_r > 0],
            environment_bucket=env,
            setup_bucket=setup,
            was_structural_win="win" in label,
            was_execution_loss=exec_drag and realized_r <= 0,
            was_timing_loss=timing,
            was_regime_mismatch_loss=regime and realized_r <= 0,
            was_spread_loss=(entry_q.spread_at_entry_bps or 0.0) > 4.0,
            was_slippage_loss=(entry_q.slippage_bps or 0.0) > self.config.EXECUTION_LOSS_SLIPPAGE_THRESHOLD_BPS,
            was_exit_mismanagement_loss=exit_mis,
            was_thesis_invalidated_fast=fast,
        )

    def finalize_lifecycle_record(self, record: TradeLifecycleRecord, entry_q: EntryQualityAssessment, path: TradePathMetrics, exit_q: ExitQualityAssessment, attr: TradeOutcomeAttribution, realized_pnl: float, realized_r: float) -> TradeLifecycleRecord:
        record.entry_quality = entry_q
        record.path_metrics = path
        record.exit_quality = exit_q
        record.attribution = attr
        record.realized_pnl = realized_pnl
        record.realized_r = realized_r
        record.status = "closed"
        record.closed_ts = datetime.now(timezone.utc)
        return record
