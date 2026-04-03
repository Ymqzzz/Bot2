from __future__ import annotations

from dataclasses import dataclass


def summarize_performance(rewards: list[float], costs: list[float]) -> dict[str, float]:
    total_return = sum(rewards)
    net_return = sum(r - c for r, c in zip(rewards, costs))
    trade_count = len(rewards)
    expectancy = (net_return / trade_count) if trade_count else 0.0
    return {
        "total_return": total_return,
        "net_return_after_costs": net_return,
        "expectancy": expectancy,
        "trade_count": trade_count,
    }


def action_confusion(baseline_actions: list[int], rl_actions: list[int]) -> dict[str, int]:
    vetoed_losers = sum(1 for b, r in zip(baseline_actions, rl_actions) if b != 0 and r == 0)
    wrong_veto_winners = sum(1 for b, r in zip(baseline_actions, rl_actions) if b == 1 and r == 0)
    return {"vetoed_losers": vetoed_losers, "wrong_veto_winners": wrong_veto_winners}


@dataclass(frozen=True)
class ImprovementPlan:
    prediction_correct: bool
    market_regime: str
    priority_actions: list[str]


def recommend_ml_improvements(
    *,
    prediction_correct: bool,
    confidence: float,
    error_magnitude: float,
    drift_score: float,
    market_regime: str,
    recent_accuracy: float,
) -> ImprovementPlan:
    """
    Build a targeted improvement checklist from post-trade prediction outcomes.

    When predictions are wrong, actions focus on error analysis and robustness.
    When predictions are right, actions focus on preserving edge while improving
    calibration and generalization so accuracy can continue to climb.
    """
    clipped_confidence = max(0.0, min(1.0, confidence))
    clipped_accuracy = max(0.0, min(1.0, recent_accuracy))

    actions: list[str] = []
    if prediction_correct:
        actions.append("Promote similar high-signal samples to training with higher weight.")
        if clipped_confidence < 0.6:
            actions.append("Improve probability calibration (isotonic/temperature scaling) for true positives.")
        else:
            actions.append("Add hard negative mining around the decision boundary to reduce future false positives.")
        if drift_score > 0.35:
            actions.append("Run drift-aware refresh to ensure today's regime edge remains stable.")
        if clipped_accuracy < 0.55:
            actions.append("Increase ensemble diversity (orthogonal features/models) to avoid fragile wins.")
        actions.append(f"Track regime-specific precision for '{market_regime}' and expand features that explain the win.")
    else:
        actions.append("Run prediction error attribution (feature contribution + execution slippage decomposition).")
        if clipped_confidence > 0.7:
            actions.append("Penalize overconfident errors using focal loss or confidence-aware reward shaping.")
        else:
            actions.append("Improve signal strength with richer microstructure and cross-asset features.")
        if error_magnitude > 0.5:
            actions.append("Apply robust losses (Huber/quantile) and outlier handling for tail events.")
        if drift_score > 0.35:
            actions.append("Trigger fast retraining with regime re-segmentation due to concept drift.")
        if clipped_accuracy < 0.55:
            actions.append("Tighten validation with walk-forward splits and stricter overfit gates before deployment.")
        actions.append(f"Add regime guardrails for '{market_regime}' to reduce repeat mistakes in similar conditions.")

    return ImprovementPlan(prediction_correct=prediction_correct, market_regime=market_regime, priority_actions=actions)
