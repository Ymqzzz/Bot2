from __future__ import annotations

from dataclasses import dataclass

from .config import ControlPlaneConfig


@dataclass(frozen=True)
class ConfluenceDecision:
    candidate_id: str
    strategy_name: str
    confluence_score: float
    risk_multiplier: float
    reason_codes: list[str]


class AdaptiveConfluenceEngine:
    """Combine strategy + context scores into a single adaptive weight."""

    def __init__(self, config: ControlPlaneConfig) -> None:
        self.config = config

    @staticmethod
    def _clip01(v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def evaluate_candidate(
        self,
        candidate: dict,
        *,
        regime_score: float,
        event_score: float,
        execution_score: float,
        correlation_penalty: float,
    ) -> ConfluenceDecision:
        ev = self._clip01(candidate.get("expected_value", 0.0))
        conf = self._clip01(candidate.get("confidence", 0.0))
        edge = self._clip01(candidate.get("edge_score", 0.5))
        regime = self._clip01(regime_score)
        event = self._clip01(event_score)
        execution = self._clip01(execution_score)
        corr_pen = self._clip01(correlation_penalty)

        w_ev = self.config.CONFLUENCE_WEIGHT_EV
        w_conf = self.config.CONFLUENCE_WEIGHT_CONFIDENCE
        w_edge = self.config.CONFLUENCE_WEIGHT_EDGE
        w_regime = self.config.CONFLUENCE_WEIGHT_REGIME
        w_event = self.config.CONFLUENCE_WEIGHT_EVENT
        w_exec = self.config.CONFLUENCE_WEIGHT_EXECUTION

        score = (
            ev * w_ev
            + conf * w_conf
            + edge * w_edge
            + regime * w_regime
            + event * w_event
            + execution * w_exec
        )
        score *= 1.0 - (corr_pen * self.config.CONFLUENCE_CORRELATION_PENALTY_WEIGHT)
        score = self._clip01(score)

        low, high = self.config.CONFLUENCE_RISK_MULTIPLIER_BOUNDS
        risk_mult = low + (high - low) * score

        reasons = ["CONFLUENCE_OK"]
        if score < self.config.CONFLUENCE_MIN_SCORE_TO_ALLOCATE:
            reasons = ["CONFLUENCE_TOO_LOW"]

        return ConfluenceDecision(
            candidate_id=str(candidate.get("candidate_id", "")),
            strategy_name=str(candidate.get("strategy_name", "")),
            confluence_score=score,
            risk_multiplier=risk_mult,
            reason_codes=reasons,
        )
