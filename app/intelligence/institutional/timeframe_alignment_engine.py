from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from app.intelligence.institutional.schemas import (
    AlignmentReport,
    Direction,
    TimeframeContribution,
    TimeframeState,
)


@dataclass(frozen=True)
class TimeframeWeightProfile:
    execution: float = 0.15
    tactical: float = 0.20
    structural: float = 0.25
    higher_timeframe: float = 0.30
    macro: float = 0.10


class HierarchicalBiasResolver:
    def __init__(self, profile: TimeframeWeightProfile | None = None) -> None:
        self.profile = profile or TimeframeWeightProfile()

    def _bucket_weight(self, timeframe: str) -> float:
        tf = timeframe.lower()
        if tf in {"15s", "30s", "1m", "2m"}:
            return self.profile.execution
        if tf in {"3m", "5m", "10m"}:
            return self.profile.tactical
        if tf in {"15m", "30m"}:
            return self.profile.structural
        if tf in {"1h", "4h"}:
            return self.profile.higher_timeframe
        return self.profile.macro

    @staticmethod
    def _direction_value(direction: Direction) -> float:
        if direction == Direction.LONG:
            return 1.0
        if direction == Direction.SHORT:
            return -1.0
        return 0.0

    def resolve(self, states: list[TimeframeState]) -> tuple[Direction, list[TimeframeContribution], float]:
        contributions: list[TimeframeContribution] = []
        weighted_sum = 0.0
        weight_total = 0.0

        for s in states:
            w = self._bucket_weight(s.timeframe)
            v = self._direction_value(s.direction)
            adjusted_weight = w * max(0.05, min(1.0, s.confidence))
            contributions.append(
                TimeframeContribution(
                    timeframe=s.timeframe,
                    weight=adjusted_weight,
                    directional_value=v,
                    confidence=s.confidence,
                )
            )
            weighted_sum += adjusted_weight * v
            weight_total += adjusted_weight

        polarity = weighted_sum / max(weight_total, 1e-9)
        if polarity > 0.15:
            direction = Direction.LONG
        elif polarity < -0.15:
            direction = Direction.SHORT
        else:
            direction = Direction.FLAT
        return direction, contributions, polarity


class CrossTimeframeConflictPenalty:
    @staticmethod
    def score(contributions: list[TimeframeContribution], polarity: float) -> float:
        if not contributions:
            return 1.0
        diffs = [abs(c.directional_value - polarity) * c.weight for c in contributions]
        normalized = sum(diffs) / max(sum(c.weight for c in contributions), 1e-9)
        return max(0.0, min(1.0, normalized / 1.3))


class AlignmentConfidenceModel:
    @staticmethod
    def score(states: list[TimeframeState], contradiction: float, polarity: float) -> float:
        if not states:
            return 0.0
        avg_conf = mean(s.confidence for s in states)
        directionality = abs(polarity)
        structural = mean((s.trend_score + s.structure_score) / 2 for s in states)
        vol_penalty = mean(max(0.0, s.volatility_score - 0.7) for s in states)
        value = avg_conf * 0.35 + directionality * 0.30 + structural * 0.25 - vol_penalty * 0.20 - contradiction * 0.25
        return max(0.0, min(1.0, value))


class MultiTimeframeAlignmentEngine:
    def __init__(self) -> None:
        self.resolver = HierarchicalBiasResolver()
        self.penalty = CrossTimeframeConflictPenalty()
        self.conf_model = AlignmentConfidenceModel()

    def evaluate(self, states: list[TimeframeState]) -> AlignmentReport:
        if not states:
            return AlignmentReport(0.0, 1.0, True, True, Direction.FLAT, [])

        bias, contributions, polarity = self.resolver.resolve(states)
        contradiction = self.penalty.score(contributions, polarity)
        confidence = self.conf_model.score(states, contradiction, polarity)

        higher = [s for s in states if s.timeframe.lower() in {"1h", "4h", "1d"}]
        htf_direction = 0.0
        if higher:
            htf_direction = mean(1.0 if s.direction == Direction.LONG else -1.0 if s.direction == Direction.SHORT else 0.0 for s in higher)

        htf_veto = (htf_direction > 0.4 and bias == Direction.SHORT) or (htf_direction < -0.4 and bias == Direction.LONG)
        veto = contradiction > 0.62 or htf_veto

        alignment = max(0.0, min(1.0, confidence * (1.0 - contradiction * 0.55)))
        return AlignmentReport(
            alignment_score=alignment,
            contradiction_severity=contradiction,
            htf_veto=htf_veto,
            veto=veto,
            refinement_bias=bias,
            contributions=contributions,
        )


__all__ = [
    "AlignmentConfidenceModel",
    "CrossTimeframeConflictPenalty",
    "HierarchicalBiasResolver",
    "MultiTimeframeAlignmentEngine",
    "TimeframeWeightProfile",
]
