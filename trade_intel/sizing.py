from __future__ import annotations

from typing import Any

from .config import TradeIntelConfig
from .models import EdgeHealthSnapshot, SizingDecision
from .reason_codes import *


class AdaptiveSizingEngine:
    """Deterministic bounded multiplier sizing.

    Each quality score input is transformed via affine clamp to avoid chaotic product behavior.
    """

    def __init__(self, config: TradeIntelConfig):
        self.config = config

    @staticmethod
    def _bounded(score: float, lo: float, hi: float) -> float:
        score = max(0.0, min(1.0, float(score)))
        return lo + (hi - lo) * score

    def recommend_size(
        self,
        candidate: dict[str, Any],
        market_intel_snapshot: dict[str, Any],
        portfolio_context: dict[str, Any],
        edge_context: list[EdgeHealthSnapshot],
        recent_performance_context: dict[str, Any],
    ) -> SizingDecision:
        base = float(candidate.get("base_risk_fraction", self.config.BASE_RISK_FRACTION_DEFAULT))
        reasons: list[str] = []

        intel = float(candidate.get("intel_quality_score", 0.5))
        exe = float(candidate.get("execution_feasibility_score", 0.5))
        regime = float(candidate.get("regime_alignment_score", 0.5))
        session_edge = float(recent_performance_context.get("session_edge_score", 0.5))
        recent_perf = float(recent_performance_context.get("recent_performance_score", 0.5))
        portfolio_score = float(portfolio_context.get("available_risk_score", 0.8))

        edge_score = 0.5 if not edge_context else min(1.0, max(0.0, sum(s.edge_score for s in edge_context) / len(edge_context)))
        edge_mult = min((s.throttle_multiplier for s in edge_context), default=1.0)

        if intel < self.config.LOW_INTEL_BLOCK_THRESHOLD:
            return self._blocked(candidate, base, [SIZE_INTEL_LOW])
        if edge_score < self.config.LOW_EDGE_BLOCK_THRESHOLD or any(s.disable_recommended for s in edge_context):
            return self._blocked(candidate, base, [SIZE_EDGE_WEAK])
        if float(market_intel_snapshot.get("execution_risk_score", 0.0)) > 0.9:
            return self._blocked(candidate, base, [SIZE_EXECUTION_BAD])

        m_intel = self._bounded(intel, 0.60, 1.20)
        m_exe = self._bounded(exe, 0.70, 1.15)
        m_regime = self._bounded(regime, 0.75, 1.15)
        m_session = self._bounded(session_edge, 0.80, 1.10)
        m_recent = self._bounded(recent_perf, 0.85, 1.10)
        m_portfolio = self._bounded(portfolio_score, 0.50, 1.00)

        if intel >= 0.7:
            reasons.append(SIZE_INTEL_HIGH)
        else:
            reasons.append(SIZE_INTEL_LOW)
        reasons.append(SIZE_EXECUTION_GOOD if exe >= 0.6 else SIZE_EXECUTION_BAD)
        reasons.append(SIZE_REGIME_ALIGNED if regime >= 0.6 else SIZE_REGIME_MISMATCH)
        reasons.append(SIZE_EDGE_STRONG if edge_score >= 0.6 else SIZE_EDGE_WEAK)
        reasons.append(SIZE_SESSION_STRONG if session_edge >= 0.6 else SIZE_SESSION_WEAK)

        event_penalty = self.config.EVENT_RISK_SIZE_PENALTY if market_intel_snapshot.get("event_risk", False) else 1.0
        spread_penalty = self.config.EXPENSIVE_SPREAD_SIZE_PENALTY if market_intel_snapshot.get("spread_expensive", False) else 1.0
        if event_penalty < 1.0:
            reasons.append(SIZE_EVENT_RISK)
        if spread_penalty < 1.0:
            reasons.append(SIZE_SPREAD_EXPENSIVE)

        total = m_intel * m_exe * m_regime * m_session * m_recent * m_portfolio * edge_mult * event_penalty * spread_penalty
        clamped = max(self.config.SIZE_MULTIPLIER_MIN, min(self.config.SIZE_MULTIPLIER_MAX, total))
        soft_cap = clamped != total
        hard_cap = m_portfolio < 1.0
        if hard_cap:
            reasons.append(SIZE_PORTFOLIO_CAP)

        rec = max(1e-6, base * clamped)
        return SizingDecision(
            trade_id=candidate.get("trade_id"),
            instrument=str(candidate.get("instrument", "")),
            strategy_name=str(candidate.get("strategy_name", "")),
            base_risk_fraction=base,
            recommended_risk_fraction=rec,
            size_multiplier_total=clamped,
            size_multiplier_intel=m_intel,
            size_multiplier_execution=m_exe,
            size_multiplier_regime=m_regime,
            size_multiplier_edge_health=edge_mult,
            size_multiplier_session=m_session,
            size_multiplier_portfolio=m_portfolio,
            size_multiplier_recent_performance=m_recent,
            hard_cap_applied=hard_cap,
            soft_cap_applied=soft_cap,
            block_trade=False,
            reason_codes=reasons,
        )

    def _blocked(self, candidate: dict[str, Any], base: float, reasons: list[str]) -> SizingDecision:
        return SizingDecision(
            trade_id=candidate.get("trade_id"),
            instrument=str(candidate.get("instrument", "")),
            strategy_name=str(candidate.get("strategy_name", "")),
            base_risk_fraction=base,
            recommended_risk_fraction=0.0,
            size_multiplier_total=0.0,
            size_multiplier_intel=0.0,
            size_multiplier_execution=0.0,
            size_multiplier_regime=0.0,
            size_multiplier_edge_health=0.0,
            size_multiplier_session=0.0,
            size_multiplier_portfolio=0.0,
            size_multiplier_recent_performance=0.0,
            hard_cap_applied=True,
            soft_cap_applied=False,
            block_trade=True,
            reason_codes=reasons,
        )
