from __future__ import annotations


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
