from app.risk.governors import GovernorState, RiskGovernor


def test_loss_streak_hard_limit_blocks_trading():
    gov = RiskGovernor(max_loss_streak_hard=4)
    state = GovernorState(loss_streak=4, realized_pnl=-10.0, unrealized_pnl=0.0)

    allowed, reason, metrics = gov.check(state, nav=100_000.0)

    assert allowed is False
    assert reason == "loss_streak_hard_limit"
    assert metrics["effective_daily_loss_limit_pct"] < gov.daily_loss_limit_pct


def test_loss_streak_risk_off_after_budget_consumption():
    gov = RiskGovernor(daily_loss_limit_pct=0.02, loss_streak_soft_limit=3)
    # $1,300 loss on $100,000 NAV => 65% usage of a 2% daily budget.
    state = GovernorState(loss_streak=3, realized_pnl=-1_300.0, unrealized_pnl=0.0)

    allowed, reason, _ = gov.check(state, nav=100_000.0)

    assert allowed is False
    assert reason == "loss_streak_risk_off"
