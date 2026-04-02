from __future__ import annotations

from dataclasses import dataclass

from app.ml.config import RewardWeights


@dataclass(frozen=True)
class RewardBreakdown:
    pnl_component: float
    risk_adjusted_component: float
    execution_quality_component: float
    signal_quality_component: float
    transaction_cost_penalty: float
    slippage_penalty: float
    drawdown_penalty: float
    overtrading_penalty: float
    tail_risk_penalty: float
    regime_mismatch_penalty: float

    @property
    def total(self) -> float:
        return (
            self.pnl_component
            + self.risk_adjusted_component
            + self.execution_quality_component
            + self.signal_quality_component
            - self.transaction_cost_penalty
            - self.slippage_penalty
            - self.drawdown_penalty
            - self.overtrading_penalty
            - self.tail_risk_penalty
            - self.regime_mismatch_penalty
        )


class RewardEngine:
    def __init__(self, weights: RewardWeights):
        self.weights = weights

    def compute(self, metrics: dict[str, float]) -> RewardBreakdown:
        pnl = metrics.get("equity_change", 0.0)
        realized_vol = max(metrics.get("realized_vol", 1.0), 1e-6)
        downside_vol = max(metrics.get("downside_vol", realized_vol), 1e-6)
        risk_adjusted = (pnl / realized_vol) - 0.2 * max(0.0, -pnl / downside_vol)
        return RewardBreakdown(
            pnl_component=self.weights.pnl * pnl,
            risk_adjusted_component=self.weights.risk_adjusted * risk_adjusted,
            execution_quality_component=self.weights.execution_quality * metrics.get("fill_quality", 0.0),
            signal_quality_component=self.weights.signal_quality * metrics.get("signal_precision_delta", 0.0),
            transaction_cost_penalty=self.weights.transaction_cost * metrics.get("transaction_cost", 0.0),
            slippage_penalty=self.weights.slippage * metrics.get("slippage", 0.0),
            drawdown_penalty=self.weights.drawdown * max(0.0, metrics.get("drawdown_delta", 0.0)),
            overtrading_penalty=self.weights.overtrading * max(0.0, metrics.get("overtrade_score", 0.0)),
            tail_risk_penalty=self.weights.tail_risk * max(0.0, metrics.get("mae_tail", 0.0)),
            regime_mismatch_penalty=self.weights.regime_mismatch * max(0.0, metrics.get("regime_mismatch", 0.0)),
        )
