from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GovernorState:
    trades_today: int = 0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    equity_peak: float = 0.0
    equity_now: float = 0.0
    intraday_drawdown_pct: float = 0.0
    loss_streak: int = 0

    @property
    def daily_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl


class RiskGovernor:
    def __init__(self, daily_loss_limit_pct: float = 0.02, max_drawdown_pct: float = 0.15, max_trades: int = 30):
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_trades = max_trades

    def _metrics(self, state: GovernorState, nav: float) -> dict[str, float]:
        loss_budget = abs(nav) * self.daily_loss_limit_pct
        loss_used = max(0.0, -state.daily_pnl)
        loss_budget_usage_pct = (loss_used / loss_budget) if loss_budget > 0 else 0.0
        return {
            "current_drawdown_pct": state.intraday_drawdown_pct,
            "loss_budget": loss_budget,
            "loss_used": loss_used,
            "loss_budget_usage_pct": loss_budget_usage_pct,
            "daily_pnl": state.daily_pnl,
            "trades_today": float(state.trades_today),
            "loss_streak": float(state.loss_streak),
        }

    def check(self, state: GovernorState, nav: float) -> tuple[bool, str, dict[str, float]]:
        metrics = self._metrics(state, nav)
        if state.trades_today >= self.max_trades:
            return False, "max_trades_reached", metrics
        if metrics["loss_budget_usage_pct"] >= 1.0:
            return False, "daily_loss_limit", metrics
        if metrics["current_drawdown_pct"] >= self.max_drawdown_pct:
            return False, "max_drawdown_limit", metrics
        return True, "", metrics
