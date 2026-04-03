from __future__ import annotations


def run_stress_replay(returns: list[float], shocks: list[float]) -> dict[str, float]:
    if not returns:
        return {"stressed_expectancy": 0.0, "stressed_drawdown": 0.0}

    shocked = [r + shocks[i % len(shocks)] if shocks else r for i, r in enumerate(returns)]
    expectancy = sum(shocked) / len(shocked)

    peak = 0.0
    equity = 0.0
    max_dd = 0.0
    for r in shocked:
        equity += r
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)

    return {"stressed_expectancy": expectancy, "stressed_drawdown": max_dd}
