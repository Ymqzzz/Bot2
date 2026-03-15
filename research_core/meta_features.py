from __future__ import annotations

from research_core.models import MetaFeatureSnapshot


def _f(value: float | None, default: float = 0.5) -> float:
    return default if value is None else float(value)


def build_meta_feature_snapshot(candidate: dict, context: dict) -> MetaFeatureSnapshot:
    calibrated_prob = context.get("calibrated_win_prob")
    calibrated_exp = context.get("calibrated_expectancy_proxy")
    failure_penalty = (
        _f(context.get("recent_false_break_rate"), 0.0)
        + _f(context.get("recent_timing_loss_rate"), 0.0)
        + _f(context.get("recent_execution_loss_rate"), 0.0)
    ) / 3.0
    meta_quality = max(0.0, min(1.0, (
        0.20 * _f(calibrated_prob, candidate.get("confidence", 0.5))
        + 0.10 * max(0.0, min(1.0, _f(calibrated_exp, candidate.get("ev_r", 0.0)) + 0.5))
        + 0.10 * _f(context.get("market_intel_quality"))
        + 0.15 * _f(context.get("execution_feasibility_score"))
        + 0.15 * _f(context.get("regime_support_score"))
        + 0.10 * _f(context.get("event_support_score"))
        + 0.10 * _f(context.get("portfolio_fit_score"))
        + 0.10 * _f(context.get("edge_score"))
        - 0.20 * failure_penalty
    )))
    return MetaFeatureSnapshot(
        candidate_id=str(candidate.get("id", "")),
        instrument=str(candidate.get("instrument", "")),
        strategy_name=str(candidate.get("strategy", "")),
        setup_type=str(candidate.get("setup_type", "unknown")),
        raw_confidence=float(candidate.get("confidence", 0.0)),
        raw_expected_value=float(candidate.get("ev_r", 0.0)),
        market_intel_quality=context.get("market_intel_quality"),
        entry_precision_score=context.get("entry_precision_score"),
        execution_feasibility_score=context.get("execution_feasibility_score"),
        regime_support_score=context.get("regime_support_score"),
        event_support_score=context.get("event_support_score"),
        portfolio_fit_score=context.get("portfolio_fit_score"),
        edge_score=context.get("edge_score"),
        calibrated_win_prob=calibrated_prob,
        calibrated_expectancy_proxy=calibrated_exp,
        recent_false_break_rate=context.get("recent_false_break_rate"),
        recent_timing_loss_rate=context.get("recent_timing_loss_rate"),
        recent_execution_loss_rate=context.get("recent_execution_loss_rate"),
        late_entry_risk=context.get("late_entry_risk"),
        spread_dislocation_risk=context.get("spread_dislocation_risk"),
        escape_risk_score=context.get("escape_risk_score"),
        meta_quality_score=meta_quality,
        reason_codes=list(context.get("reason_codes", [])),
    )
