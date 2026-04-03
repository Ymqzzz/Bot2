from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from app.intelligence.institutional.schemas import (
    Direction,
    ScenarioOutcome,
    ScenarioPath,
    StressDistribution,
    StressReport,
    TradeProposal,
)


@dataclass(frozen=True)
class PathTemplate:
    name: str
    vol_multiplier: float
    spread_multiplier: float
    slippage_bps: float
    fill_delay_bars: int
    partial_fill_ratio: float
    shock_direction: Direction
    correlated_shock: float
    liquidity_gap: float


class PathPerturbationLibrary:
    def __init__(self) -> None:
        self.templates: list[PathTemplate] = [
            PathTemplate("base", 1.0, 1.0, 0.0, 0, 1.0, Direction.FLAT, 0.0, 0.0),
            PathTemplate("spread_widening", 1.1, 1.8, 1.8, 0, 1.0, Direction.FLAT, 0.1, 0.15),
            PathTemplate("vol_expansion", 1.9, 1.3, 2.5, 1, 0.95, Direction.FLAT, 0.2, 0.2),
            PathTemplate("fill_delay", 1.0, 1.1, 4.5, 3, 1.0, Direction.FLAT, 0.05, 0.1),
            PathTemplate("partial_fill", 1.2, 1.0, 2.0, 1, 0.55, Direction.FLAT, 0.15, 0.05),
            PathTemplate("false_breakout", 1.7, 1.2, 4.0, 1, 0.9, Direction.SHORT, 0.35, 0.35),
            PathTemplate("mean_reversion_failure", 1.6, 1.25, 4.2, 1, 0.8, Direction.SHORT, 0.3, 0.2),
            PathTemplate("regime_flip", 2.2, 1.5, 6.5, 2, 0.75, Direction.SHORT, 0.5, 0.35),
            PathTemplate("correlated_shock", 1.8, 1.7, 7.2, 2, 0.7, Direction.SHORT, 0.8, 0.3),
            PathTemplate("liquidity_vacuum", 2.6, 2.5, 9.0, 3, 0.6, Direction.SHORT, 0.6, 0.65),
            PathTemplate("bull_run", 1.4, 1.0, 1.2, 0, 1.0, Direction.LONG, 0.2, 0.0),
            PathTemplate("orderly_trend", 0.9, 0.85, 0.8, 0, 1.0, Direction.LONG, 0.1, 0.0),
        ]

    def build_paths(self, n_paths: int) -> list[ScenarioPath]:
        out: list[ScenarioPath] = []
        for i in range(n_paths):
            t = self.templates[i % len(self.templates)]
            out.append(
                ScenarioPath(
                    scenario_name=t.name,
                    vol_multiplier=t.vol_multiplier,
                    spread_multiplier=t.spread_multiplier,
                    slippage_bps=t.slippage_bps,
                    fill_delay_bars=t.fill_delay_bars,
                    partial_fill_ratio=t.partial_fill_ratio,
                    shock_direction=t.shock_direction,
                    correlated_shock=t.correlated_shock,
                    liquidity_gap=t.liquidity_gap,
                )
            )
        return out


class ScenarioGenerator:
    def __init__(self, library: PathPerturbationLibrary | None = None) -> None:
        self.library = library or PathPerturbationLibrary()

    def generate(self, proposal: TradeProposal, n_paths: int = 60) -> list[ScenarioPath]:
        n = max(20, min(100, n_paths))
        return self.library.build_paths(n)


class ForwardStressEngine:
    def evaluate(self, proposal: TradeProposal, scenarios: list[ScenarioPath]) -> StressReport:
        outcomes = [self._simulate_path(proposal, p) for p in scenarios]
        dist = self._distribution(outcomes)
        robustness, fragility, notes = self._score_distribution(dist)
        fragile = fragility > 0.60 or robustness < 0.45
        return StressReport(
            path_count=len(scenarios),
            robustness_score=robustness,
            fragility_score=fragility,
            fragile=fragile,
            distribution=dist,
            notes=notes,
        )

    def _simulate_path(self, proposal: TradeProposal, path: ScenarioPath) -> ScenarioOutcome:
        risk = abs(proposal.entry - proposal.stop)
        reward = abs(proposal.target - proposal.entry)
        if risk <= 1e-12:
            return ScenarioOutcome(path.scenario_name, -3.0, 3.0, 0.0, 1.0)

        rr = reward / risk
        side_sign = 1.0 if proposal.side == Direction.LONG else -1.0
        shock_sign = 1.0 if path.shock_direction == Direction.LONG else -1.0 if path.shock_direction == Direction.SHORT else 0.0

        spread = proposal.features.get("spread", 0.0001) * path.spread_multiplier
        slippage = proposal.entry * (path.slippage_bps / 10_000.0)
        total_cost = (spread + slippage) / max(risk, 1e-9)

        fill_quality = max(0.0, min(1.0, path.partial_fill_ratio - path.fill_delay_bars * 0.05 - path.liquidity_gap * 0.25))
        volatility_drag = max(0.0, path.vol_multiplier - 1.0) * 0.22
        correlated_drag = path.correlated_shock * 0.35
        drift_alpha = proposal.features.get("drift_alpha", 0.10)
        structure_support = proposal.features.get("structure_support", 0.5)
        breakout_quality = proposal.features.get("breakout_quality", 0.5)

        direction_effect = side_sign * shock_sign * 0.35
        base_return = rr * (0.4 + 0.6 * fill_quality)
        alpha_return = drift_alpha * 0.6 + structure_support * 0.3 + breakout_quality * 0.25

        pnl_r = base_return + alpha_return + direction_effect - total_cost - volatility_drag - correlated_drag
        max_drawdown_r = max(0.0, volatility_drag * 1.8 + correlated_drag * 1.2 + path.liquidity_gap * 0.8 + max(0.0, -direction_effect))
        break_prob = min(1.0, 0.15 + path.liquidity_gap * 0.35 + path.correlated_shock * 0.25 + max(0.0, path.vol_multiplier - 1.5) * 0.30)

        return ScenarioOutcome(
            scenario_name=path.scenario_name,
            pnl_r=pnl_r,
            max_drawdown_r=max_drawdown_r,
            fill_quality=fill_quality,
            break_probability=break_prob,
        )

    def _distribution(self, outcomes: list[ScenarioOutcome]) -> StressDistribution:
        ordered = sorted(outcomes, key=lambda x: x.pnl_r)
        vals = [o.pnl_r for o in ordered]
        draws = sorted(o.max_drawdown_r for o in ordered)

        def pct(v: list[float], p: float) -> float:
            if not v:
                return 0.0
            idx = max(0, min(len(v) - 1, int(round((len(v) - 1) * p))))
            return v[idx]

        return StressDistribution(
            outcomes=ordered,
            expected_r=mean(vals) if vals else 0.0,
            median_r=pct(vals, 0.5),
            p10_r=pct(vals, 0.1),
            p5_r=pct(vals, 0.05),
            worst_r=vals[0] if vals else 0.0,
            drawdown_p95=pct(draws, 0.95),
        )

    def _score_distribution(self, dist: StressDistribution) -> tuple[float, float, list[str]]:
        notes: list[str] = []
        robustness = 0.50
        fragility = 0.50

        robustness += max(-0.3, min(0.3, dist.expected_r * 0.20))
        robustness += max(-0.25, min(0.25, dist.p10_r * 0.22))
        robustness += max(-0.20, min(0.20, dist.median_r * 0.15))
        robustness -= max(0.0, dist.drawdown_p95 - 1.2) * 0.10

        fragility += max(0.0, -dist.p5_r) * 0.15
        fragility += max(0.0, -dist.worst_r) * 0.10
        fragility += max(0.0, dist.drawdown_p95 - 1.1) * 0.15

        if dist.p10_r < -0.75:
            notes.append("left_tail_heavy")
        if dist.worst_r < -1.8:
            notes.append("extreme_worst_case")
        if dist.drawdown_p95 > 1.5:
            notes.append("drawdown_instability")

        robustness = max(0.0, min(1.0, robustness))
        fragility = max(0.0, min(1.0, fragility))
        return robustness, fragility, notes


__all__ = [
    "ForwardStressEngine",
    "PathPerturbationLibrary",
    "ScenarioGenerator",
]
