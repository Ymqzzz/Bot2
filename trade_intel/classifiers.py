from __future__ import annotations

from . import reason_codes as rc


def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def classify_entry_quality(
    *,
    slippage_bps: float,
    spread_bps: float,
    distance_struct_bps: float,
    distance_profile_bps: float,
    move_spent_fraction: float,
    adverse_selection_score: float,
    passive_improvement: bool,
) -> tuple[str, float, list[str]]:
    score = 1.0
    score -= _clip(slippage_bps / 6.0) * 0.25
    score -= _clip(spread_bps / 8.0) * 0.20
    score -= _clip(distance_struct_bps / 20.0) * 0.15
    score -= _clip(distance_profile_bps / 20.0) * 0.10
    score -= _clip(move_spent_fraction) * 0.20
    score -= _clip(adverse_selection_score) * 0.20
    if passive_improvement:
        score += 0.05
    score = _clip(score)
    reasons: list[str] = []
    if distance_struct_bps <= 5:
        reasons.append(rc.ENTRY_STRUCTURAL_CONFLUENCE)
    if distance_profile_bps <= 5:
        reasons.append(rc.ENTRY_PROFILE_CONFLUENCE)
    if spread_bps > 4:
        reasons.append(rc.ENTRY_POOR_SPREAD)
    if slippage_bps > 2:
        reasons.append(rc.ENTRY_HIGH_SLIPPAGE)
    if adverse_selection_score > 0.5:
        reasons.append(rc.ENTRY_ADVERSE_SELECTION)
    if move_spent_fraction > 0.65:
        reasons.append(rc.ENTRY_LATE_AFTER_EXPANSION)

    if adverse_selection_score > 0.7:
        return "adversely_selected", score, reasons
    if move_spent_fraction > 0.8:
        return "late", score, reasons
    if slippage_bps > 4 and spread_bps > 5:
        return "chased", score, reasons + [rc.ENTRY_CHASED]
    if score >= 0.85:
        return "excellent", score, reasons + [rc.ENTRY_CLEAN_AT_LEVEL]
    if score >= 0.70:
        return "good", score, reasons
    if score >= 0.55:
        return "acceptable", score, reasons
    return "poor", score, reasons


def classify_exit_quality(
    *,
    captured_mfe_fraction: float,
    gaveback_fraction: float,
    exit_at_structure: bool,
    exit_at_profile: bool,
    due_to_time_stop: bool,
    due_to_trailing: bool,
    due_to_execution_dislocation: bool,
) -> tuple[str, float, list[str]]:
    score = 0.6 * _clip(captured_mfe_fraction) + 0.4 * (1.0 - _clip(gaveback_fraction))
    reasons: list[str] = []
    if exit_at_structure:
        reasons.append(rc.EXIT_STRUCTURE_REJECTION)
    if exit_at_profile:
        reasons.append(rc.EXIT_PARTIAL_AT_PROFILE)
    if due_to_time_stop:
        reasons.append(rc.EXIT_TIME_STOP)
    if due_to_trailing:
        reasons.append(rc.EXIT_TRAILING_STOP)
    if due_to_execution_dislocation:
        reasons.append(rc.EXIT_EXECUTION_DISLOCATION)

    if due_to_execution_dislocation:
        return "execution_forced_exit", score, reasons
    if captured_mfe_fraction >= 0.85 and gaveback_fraction <= 0.2:
        return "excellent_capture", score, reasons + [rc.EXIT_AT_TARGET]
    if exit_at_structure or exit_at_profile:
        return "good_structural_exit", score, reasons
    if gaveback_fraction >= 0.6:
        return "gave_back_too_much", score, reasons + [rc.EXIT_MFE_GIVEBACK_CONTROL]
    if due_to_time_stop and captured_mfe_fraction < 0.2:
        return "bad_hold", score, reasons
    if due_to_trailing and captured_mfe_fraction > 0.5:
        return "stopped_appropriately", score, reasons
    if captured_mfe_fraction < 0.25:
        return "premature_exit", score, reasons
    return "acceptable", score, reasons


def classify_trade_outcome(
    *,
    realized_r: float,
    entry_quality_score: float,
    exit_quality_score: float,
    fast_invalidated: bool,
    execution_drag: bool,
    timing_loss: bool,
    regime_mismatch: bool,
    exit_mismanaged: bool,
) -> tuple[str, float, str, list[str]]:
    score = _clip(0.5 + 0.35 * realized_r + 0.1 * entry_quality_score + 0.05 * exit_quality_score)
    reasons: list[str] = []
    driver = "balanced"
    if fast_invalidated:
        return "fast_thesis_failure", score, rc.ATTR_FAST_THESIS_FAILURE, [rc.ATTR_FAST_THESIS_FAILURE]
    if realized_r >= 1.2 and entry_quality_score >= 0.7:
        return "high_quality_win", score, rc.ATTR_STRUCTURAL_WIN, [rc.ATTR_STRUCTURAL_WIN]
    if realized_r > 0:
        if execution_drag:
            return "execution_dragged_win", score, rc.ATTR_SLIPPAGE_COST_LOSS, [rc.ATTR_SLIPPAGE_COST_LOSS]
        return "structural_win", score, rc.ATTR_STRUCTURAL_WIN, [rc.ATTR_STRUCTURAL_WIN]
    if execution_drag:
        driver = rc.ATTR_EXECUTION_LOSS
        reasons.append(rc.ATTR_EXECUTION_LOSS)
        return "execution_loss", score, driver, reasons
    if timing_loss:
        return "timing_loss", score, rc.ATTR_TIMING_LOSS, [rc.ATTR_TIMING_LOSS]
    if regime_mismatch:
        return "regime_loss", score, rc.ATTR_REGIME_MISMATCH, [rc.ATTR_REGIME_MISMATCH]
    if exit_mismanaged:
        return "exit_mismanagement_loss", score, rc.ATTR_EXIT_MISMANAGEMENT, [rc.ATTR_EXIT_MISMANAGEMENT]
    return "small_clean_loss", score, driver, reasons


def classify_environment_bucket(regime: str, session: str, spread_regime: str, event_state: str, execution_regime: str) -> str:
    return f"{regime}|{session}|spr:{spread_regime}|evt:{event_state}|exe:{execution_regime}"


def classify_setup_bucket(strategy: str, subtype: str | None, structure_context: str, profile_context: str, trigger_family: str) -> str:
    st = subtype or "default"
    return f"{strategy}|{st}|struct:{structure_context}|profile:{profile_context}|trig:{trigger_family}"
