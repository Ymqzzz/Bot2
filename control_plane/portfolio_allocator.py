from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

from .config import ControlPlaneConfig
from .correlation import CorrelationEngine
from .models import AllocationCandidate, AllocationDecision, EventDecision, ExecutionDecision, PortfolioStateSnapshot, RegimeDecision
from .reason_codes import *


class PortfolioAllocator:
    def __init__(self, config: ControlPlaneConfig, correlation_engine: CorrelationEngine):
        self.config = config
        self.correlation_engine = correlation_engine

    def build_portfolio_state(self, open_positions: list[dict], candidate_pool: list[AllocationCandidate], current_allocations: dict[str, float] | None = None) -> PortfolioStateSnapshot:
        now = datetime.now(timezone.utc)
        instrument_weights = defaultdict(float)
        currency_net = defaultdict(float)
        currency_gross = defaultdict(float)
        macro = defaultdict(float)
        for p in open_positions:
            ins = p.get("instrument", "")
            u = float(p.get("units", 0.0))
            w = abs(u) / 100000
            instrument_weights[ins] += w
            base, quote = ins.split("_") if "_" in ins else (ins[:3], ins[3:])
            sign = 1.0 if u >= 0 else -1.0
            currency_net[base] += sign * w
            currency_net[quote] -= sign * w
            currency_gross[base] += w
            currency_gross[quote] += w
        heat = sum(abs(v) for v in instrument_weights.values())
        return PortfolioStateSnapshot(
            asof=now,
            open_positions=open_positions,
            instrument_weights=dict(instrument_weights),
            currency_net_exposure=dict(currency_net),
            currency_gross_exposure=dict(currency_gross),
            macro_cluster_exposure=dict(macro),
            portfolio_heat=float(heat),
            correlation_matrix={},
            drawdown_state="normal",
            risk_budget_remaining=max(0.0, 0.05 - float(heat)),
        )

    def score_candidate_priority(self, candidate: AllocationCandidate, regime_decision: RegimeDecision, event_decision: EventDecision, execution_decision: ExecutionDecision, edge_snapshot: dict | None) -> float:
        cfg = self.config
        base = (
            candidate.expected_value * cfg.ALLOC_PRIORITY_EV_WEIGHT
            + candidate.execution_score * cfg.ALLOC_PRIORITY_EXEC_WEIGHT
            + candidate.edge_score * cfg.ALLOC_PRIORITY_EDGE_WEIGHT
            + candidate.regime_score * cfg.ALLOC_PRIORITY_REGIME_WEIGHT
            + candidate.event_score * cfg.ALLOC_PRIORITY_EVENT_WEIGHT
        )
        mult = regime_decision.strategy_weight_multipliers.get(candidate.strategy_name, 1.0) * event_decision.event_risk_multiplier
        if not execution_decision.allow_entry:
            mult *= 0.1
        return float(base * mult)

    def allocate(self, candidate_pool: list[AllocationCandidate], portfolio_state: PortfolioStateSnapshot) -> AllocationDecision:
        now = datetime.now(timezone.utc)
        approved: list[str] = []
        blocked: list[str] = []
        resized: list[str] = []
        allocs: dict[str, float] = {}
        reasons: list[str] = []
        cluster_alloc = defaultdict(float)
        corr_pen = {}
        instrument_count = Counter()
        usd_net = portfolio_state.currency_net_exposure.get("USD", 0.0)
        heat = portfolio_state.portfolio_heat

        for c in sorted(candidate_pool, key=lambda x: (-(x.priority_score or 0.0), x.candidate_id)):
            if len(approved) >= self.config.ALLOC_MAX_NEW_TRADES_PER_CYCLE:
                blocked.append(c.candidate_id)
                reasons.append(ALLOC_RISK_BUDGET_EXHAUSTED)
                continue
            if (c.priority_score or 0.0) < self.config.ALLOC_MIN_PRIORITY_SCORE:
                blocked.append(c.candidate_id)
                reasons.append(ALLOC_LOW_PRIORITY)
                continue
            if instrument_count[c.instrument] >= self.config.ALLOC_MAX_INSTRUMENT_DUPLICATION:
                blocked.append(c.candidate_id)
                reasons.append(ALLOC_BLOCKED_BY_PORTFOLIO_FIT)
                continue
            risk = c.risk_fraction_requested
            cl = c.macro_cluster_key or "other"
            if cluster_alloc[cl] + risk > self.config.ALLOC_MAX_SINGLE_MACRO_CLUSTER_RISK and self.config.ALLOC_ENABLE_RESIZING:
                new_risk = max(0.0, self.config.ALLOC_MAX_SINGLE_MACRO_CLUSTER_RISK - cluster_alloc[cl])
                if new_risk > 0:
                    risk = new_risk
                    resized.append(c.candidate_id)
                    reasons.append(ALLOC_RESIZED_FOR_CLUSTER)
                else:
                    blocked.append(c.candidate_id)
                    reasons.append(ALLOC_MACRO_DUPLICATION)
                    continue
            new_usd = usd_net + c.currency_exposure_map.get("USD", 0.0)
            if abs(new_usd) > self.config.ALLOC_MAX_USD_NET_EXPOSURE:
                if self.config.ALLOC_ENABLE_RESIZING:
                    shrink = max(0.0, self.config.ALLOC_MAX_USD_NET_EXPOSURE - abs(usd_net))
                    risk = min(risk, shrink)
                    if risk <= 0:
                        blocked.append(c.candidate_id)
                        reasons.append(ALLOC_USD_CONCENTRATION_CAP)
                        continue
                    resized.append(c.candidate_id)
                    reasons.append(ALLOC_RESIZED_FOR_CONCENTRATION)
                else:
                    blocked.append(c.candidate_id)
                    reasons.append(ALLOC_USD_CONCENTRATION_CAP)
                    continue
            if heat + risk > portfolio_state.portfolio_heat + portfolio_state.risk_budget_remaining:
                blocked.append(c.candidate_id)
                reasons.append(ALLOC_PORTFOLIO_HEAT_CAP)
                continue
            approved.append(c.candidate_id)
            allocs[c.candidate_id] = risk
            instrument_count[c.instrument] += 1
            cluster_alloc[cl] += risk
            usd_net = new_usd
            heat += risk
            reasons.append(ALLOC_HIGH_PRIORITY)
            corr_pen[c.candidate_id] = max(0.0, 1.0 - (c.portfolio_fit_score or 1.0))

        return AllocationDecision(
            asof=now,
            approved_candidate_ids=approved,
            blocked_candidate_ids=blocked,
            resized_candidate_ids=resized,
            final_risk_allocations=allocs,
            portfolio_heat_before=portfolio_state.portfolio_heat,
            portfolio_heat_after=heat,
            usd_net_exposure_before=portfolio_state.currency_net_exposure.get("USD", 0.0),
            usd_net_exposure_after=usd_net,
            macro_cluster_allocations=dict(cluster_alloc),
            correlation_penalties=corr_pen,
            reason_codes=list(dict.fromkeys(reasons)),
        )
