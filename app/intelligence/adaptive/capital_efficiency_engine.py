from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.base import clamp
from app.intelligence.adaptive.adaptive_types import CapitalEfficiencyReport
from app.intelligence.adaptive.capital_lockup_tracker import CapitalLockupTracker
from app.intelligence.adaptive.liquidation_stress_projection import LiquidationStressProjection
from app.intelligence.adaptive.margin_pressure_model import MarginPressureModel
from app.intelligence.adaptive.opportunity_cost_allocator import OpportunityCostAllocator


@dataclass
class CapitalEfficiencyEngine:
    margin_model: MarginPressureModel = MarginPressureModel()
    lockup_tracker: CapitalLockupTracker = CapitalLockupTracker()
    opportunity_allocator: OpportunityCostAllocator = OpportunityCostAllocator()
    liquidation_projection: LiquidationStressProjection = LiquidationStressProjection()

    def evaluate(self, *, features: dict[str, float], context: dict, candidate_strategy: str, expected_edge: float) -> CapitalEfficiencyReport:
        account_equity = max(1.0, float(context.get("account_equity", 100_000.0)))
        free_margin = max(0.0, float(context.get("free_margin", account_equity * 0.65)))
        notional = max(1.0, float(context.get("candidate_notional", account_equity * 0.1)))
        leverage = max(1.0, float(context.get("effective_leverage", 10.0)))
        correlation_stress = clamp(float(context.get("correlation_stress", features.get("correlation_stress", 0.2))))
        concentration = clamp(float(context.get("strategy_concentration", 0.2)))

        compression = self.margin_model.project_margin_compression(
            realized_vol=float(features.get("realized_vol", 0.2)),
            vol_percentile=float(features.get("atr_percentile", 0.5)),
            correlation_stress=correlation_stress,
            concentration=concentration,
        )
        incremental = self.margin_model.incremental_margin(notional=notional, leverage=leverage, compression=compression)
        free_after = max(0.0, free_margin - incremental)
        headroom = clamp(free_after / account_equity)

        raw_lockups = dict(context.get("capital_lockup_by_family", {}))
        _, lockups = self.lockup_tracker.aggregate_lockup(raw_lockups)
        lockups[candidate_strategy] = lockups.get(candidate_strategy, 0.0) + incremental

        queue = list(context.get("queued_trades", []))
        oc_penalty = self.opportunity_allocator.penalty(expected_edge=expected_edge, incremental_margin=incremental, queue=queue)

        stress_drawdown = clamp(float(context.get("stress_drawdown", 0.35)))
        cascade_risk = self.liquidation_projection.cascade_risk(
            free_margin_after_fill=free_after,
            equity=account_equity,
            stress_drawdown=stress_drawdown,
            correlation_stress=correlation_stress,
        )

        edge_per_capital = expected_edge / max(incremental, 1e-9)
        efficiency = clamp(edge_per_capital * 5.0)
        efficiency = clamp(efficiency * (1.0 - 0.45 * oc_penalty) * (1.0 - 0.35 * cascade_risk))

        reasons: list[str] = []
        if headroom < 0.15:
            reasons.append("MARGIN_HEADROOM_COMPRESSED")
        if oc_penalty > 0.4:
            reasons.append("OPPORTUNITY_COST_HIGH")
        if cascade_risk > 0.55:
            reasons.append("LIQUIDATION_CASCADE_RISK")
        if efficiency > 0.65:
            reasons.append("CAPITAL_EFFICIENT")

        return CapitalEfficiencyReport(
            capital_efficiency_score=efficiency,
            expected_edge=expected_edge,
            incremental_margin=incremental,
            free_margin_after_fill=free_after,
            margin_headroom_ratio=headroom,
            liquidation_cascade_risk=cascade_risk,
            opportunity_cost_penalty=oc_penalty,
            lockup_by_family=lockups,
            reason_codes=reasons,
        )
