from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GovernorState:
    trades_today: int = 0
    daily_pnl: float = 0.0
    equity_peak: float = 0.0
    equity_now: float = 0.0


class RiskGovernor:
    def __init__(self, daily_loss_limit_pct: float = 0.02, max_drawdown_pct: float = 0.15, max_trades: int = 30):
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_trades = max_trades

    def check(self, state: GovernorState, nav: float) -> tuple[bool, str]:
        if state.trades_today >= self.max_trades:
            return False, "max_trades_reached"
        if state.daily_pnl <= -abs(nav) * self.daily_loss_limit_pct:
            return False, "daily_loss_limit"
        if state.equity_peak > 0:
            dd = (state.equity_now - state.equity_peak) / state.equity_peak
            if dd <= -self.max_drawdown_pct:
                return False, "max_drawdown_limit"
        return True, ""
