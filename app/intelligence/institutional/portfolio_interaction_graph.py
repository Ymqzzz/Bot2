from __future__ import annotations

from collections import defaultdict
from statistics import mean

from app.intelligence.institutional.schemas import (
    InteractionEdge,
    PortfolioGraphReport,
    PositionNode,
)


class FactorExposureMapper:
    @staticmethod
    def exposure_vector(node: PositionNode) -> dict[str, float]:
        return {
            "risk_on": node.quantity * node.beta_risk_on,
            "usd": node.quantity * node.usd_beta,
            "rates": node.quantity * node.rates_beta,
            "commodities": node.quantity * node.commodities_beta,
        }


class ThesisOverlapDetector:
    @staticmethod
    def same_thesis(a: PositionNode, b: PositionNode) -> float:
        base = 1.0 if a.thesis_family == b.thesis_family else 0.0
        regime = 0.35 if a.regime_tag == b.regime_tag else 0.0
        event = 0.20 * min(a.event_vulnerability, b.event_vulnerability)
        return min(1.0, base * 0.65 + regime + event)


class PortfolioConcentrationPenalty:
    @staticmethod
    def compute(nodes: list[PositionNode], edges: list[InteractionEdge]) -> tuple[float, float, float]:
        if not nodes:
            return 0.0, 0.0, 0.0

        abs_notional = [abs(n.notional) for n in nodes]
        total = sum(abs_notional)
        by_thesis: dict[str, float] = defaultdict(float)
        for n in nodes:
            by_thesis[n.thesis_family] += abs(n.notional)
        top_thesis_ratio = max(by_thesis.values()) / max(total, 1e-9)

        factor_edges = mean(e.factor_overlap_score for e in edges) if edges else 0.0
        stop_edges = mean(e.stop_overlap_score for e in edges) if edges else 0.0

        concentration = min(1.0, top_thesis_ratio * 0.65 + factor_edges * 0.25 + stop_edges * 0.10)
        fragility = min(1.0, concentration * 0.6 + stop_edges * 0.25 + factor_edges * 0.15)
        return concentration, top_thesis_ratio, fragility


class CrossPositionStressModel:
    @staticmethod
    def liquidation_correlation(a: PositionNode, b: PositionNode) -> float:
        stop_overlap = max(0.0, 1.0 - abs(a.stop_distance_r - b.stop_distance_r))
        vulnerability = (a.event_vulnerability + b.event_vulnerability) / 2.0
        notional_balance = min(abs(a.notional), abs(b.notional)) / max(abs(a.notional), abs(b.notional), 1e-9)
        return min(1.0, stop_overlap * 0.45 + vulnerability * 0.35 + notional_balance * 0.20)


class PortfolioInteractionGraph:
    def __init__(self) -> None:
        self.factor_mapper = FactorExposureMapper()
        self.thesis_detector = ThesisOverlapDetector()
        self.penalty = PortfolioConcentrationPenalty()
        self.cross_stress = CrossPositionStressModel()

    def evaluate(self, open_positions: list[PositionNode], candidate: PositionNode | None = None) -> PortfolioGraphReport:
        nodes = [*open_positions]
        if candidate is not None:
            nodes.append(candidate)

        edges: list[InteractionEdge] = []
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a = nodes[i]
                b = nodes[j]
                factor_overlap = self._factor_overlap(a, b)
                same_thesis = self.thesis_detector.same_thesis(a, b)
                stop_overlap = max(0.0, 1.0 - abs(a.stop_distance_r - b.stop_distance_r))
                liq = self.cross_stress.liquidation_correlation(a, b)
                edges.append(
                    InteractionEdge(
                        src_position_id=a.position_id,
                        dst_position_id=b.position_id,
                        same_thesis_score=same_thesis,
                        factor_overlap_score=factor_overlap,
                        stop_overlap_score=stop_overlap,
                        liquidation_correlation=liq,
                    )
                )

        concentration, same_thesis_ratio, fragility = self.penalty.compute(nodes, edges)
        factor_crowding = mean(e.factor_overlap_score for e in edges) if edges else 0.0
        stop_overlap_score = mean(e.stop_overlap_score for e in edges) if edges else 0.0

        suggestions: list[str] = []
        if same_thesis_ratio > 0.65:
            suggestions.append("reduce_same_thesis_exposure")
        if factor_crowding > 0.60:
            suggestions.append("compress_common_factor_capital")
        if stop_overlap_score > 0.55:
            suggestions.append("stagger_stop_zones")
        if fragility > 0.70:
            suggestions.append("activate_cluster_max_exposure_control")

        return PortfolioGraphReport(
            node_count=len(nodes),
            edge_count=len(edges),
            concentration_score=concentration,
            same_thesis_ratio=same_thesis_ratio,
            factor_crowding_score=factor_crowding,
            stop_overlap_score=stop_overlap_score,
            fragility_score=fragility,
            netting_suggestions=suggestions,
            edges=edges,
        )

    def _factor_overlap(self, a: PositionNode, b: PositionNode) -> float:
        va = self.factor_mapper.exposure_vector(a)
        vb = self.factor_mapper.exposure_vector(b)
        num = sum(va[k] * vb[k] for k in va)
        den_a = sum(abs(va[k]) for k in va)
        den_b = sum(abs(vb[k]) for k in vb)
        if den_a == 0 or den_b == 0:
            return 0.0
        cosine_like = num / (den_a * den_b)
        return max(0.0, min(1.0, abs(cosine_like) * 2.0))


__all__ = [
    "CrossPositionStressModel",
    "FactorExposureMapper",
    "PortfolioConcentrationPenalty",
    "PortfolioInteractionGraph",
    "ThesisOverlapDetector",
]
