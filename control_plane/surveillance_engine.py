from __future__ import annotations

from dataclasses import dataclass

from .config import ControlPlaneConfig


@dataclass(frozen=True)
class SurveillanceDecision:
    candidate_id: str
    instrument: str
    toxicity_score: float
    allow_trade: bool
    risk_multiplier: float
    reason_codes: list[str]


class SurveillanceEngine:
    """Detect toxic flow/manipulation style conditions and gate risk."""

    def __init__(self, config: ControlPlaneConfig) -> None:
        self.config = config

    @staticmethod
    def _clip01(v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def evaluate_candidate(self, candidate: dict, market_snapshot: dict | None) -> SurveillanceDecision:
        snapshot = market_snapshot or {}
        tox = self._clip01(snapshot.get("toxicity_score", snapshot.get("vpin", 0.0)))
        spoof = self._clip01(snapshot.get("spoofing_risk", 0.0))
        trap = self._clip01(snapshot.get("liquidity_trap_risk", 0.0))

        toxicity = self._clip01(max(tox, 0.8 * spoof, 0.8 * trap))
        reasons = ["SURVEILLANCE_OK"]
        allow = True
        risk_mult = 1.0

        if toxicity >= self.config.SURVEILLANCE_MAX_TOXICITY:
            allow = False
            risk_mult = 0.0
            reasons = ["SURVEILLANCE_BLOCK_TOXIC_FLOW"]
        elif toxicity >= self.config.SURVEILLANCE_SOFT_TOXICITY:
            risk_mult = 0.5
            reasons = ["SURVEILLANCE_SOFT_THROTTLE"]

        return SurveillanceDecision(
            candidate_id=str(candidate.get("candidate_id", "")),
            instrument=str(candidate.get("instrument", "")),
            toxicity_score=toxicity,
            allow_trade=allow,
            risk_multiplier=risk_mult,
            reason_codes=reasons,
        )
