from __future__ import annotations

from .regime_segment_report import sharpe_by_regime
from .stress_scenario_replay import run_stress_replay


def validation_report_bundle(returns_by_regime: list[tuple[str, float]], raw_returns: list[float], shocks: list[float]) -> dict[str, object]:
    return {
        "sharpe_by_regime": sharpe_by_regime(returns_by_regime),
        "stress": run_stress_replay(raw_returns, shocks),
    }
