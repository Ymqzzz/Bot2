from __future__ import annotations

from collections import defaultdict
from statistics import mean

from app.intelligence.institutional.schemas import (
    Direction,
    EnsembleDecision,
    FamilyConsensus,
    ThesisVote,
)


class ThesisFamilyModel:
    def family_of(self, strategy_name: str) -> str:
        s = strategy_name.lower()
        if "trend" in s:
            return "trend_following"
        if "mean" in s or "reversion" in s:
            return "mean_reversion"
        if "sweep" in s or "liquidity" in s:
            return "liquidity_sweep"
        if "breakout" in s:
            return "breakout_continuation"
        if "event" in s:
            return "event_reaction"
        if "vol" in s:
            return "volatility_expansion"
        return "other"


class FamilyConfidenceAggregator:
    def aggregate(self, votes: list[ThesisVote]) -> list[FamilyConsensus]:
        grouped: dict[str, list[ThesisVote]] = defaultdict(list)
        for vote in votes:
            grouped[vote.thesis_family].append(vote)

        out: list[FamilyConsensus] = []
        for family, family_votes in grouped.items():
            if not family_votes:
                continue
            scores = []
            for v in family_votes:
                sign = 1.0 if v.direction == Direction.LONG else -1.0 if v.direction == Direction.SHORT else 0.0
                scores.append(sign * v.confidence * max(0.05, v.weight))

            net = mean(scores)
            abs_conf = mean(abs(s) for s in scores)
            disagreement = mean(abs(s - net) for s in scores)
            if net > 0.12:
                direction = Direction.LONG
            elif net < -0.12:
                direction = Direction.SHORT
            else:
                direction = Direction.FLAT
            conf = max(0.0, min(1.0, abs_conf * (1.0 - min(1.0, disagreement))))

            out.append(
                FamilyConsensus(
                    thesis_family=family,
                    net_direction=direction,
                    confidence=conf,
                    disagreement=min(1.0, disagreement),
                    voters=len(family_votes),
                )
            )

        out.sort(key=lambda x: x.confidence, reverse=True)
        return out


class InterFamilyConflictEngine:
    def score(self, family_consensus: list[FamilyConsensus]) -> float:
        if not family_consensus:
            return 1.0

        values: list[float] = []
        for fc in family_consensus:
            sign = 1.0 if fc.net_direction == Direction.LONG else -1.0 if fc.net_direction == Direction.SHORT else 0.0
            values.append(sign * fc.confidence)

        if len(values) == 1:
            return 0.0

        avg = mean(values)
        spread = mean(abs(v - avg) for v in values)
        flat_ratio = sum(1 for v in values if abs(v) < 0.08) / len(values)
        return max(0.0, min(1.0, spread * 1.35 + flat_ratio * 0.25))


class ThesisWeightAdapter:
    def adapt(self, family_consensus: list[FamilyConsensus], conflict: float) -> float:
        if not family_consensus:
            return 0.0
        top = family_consensus[0].confidence
        avg = mean(f.confidence for f in family_consensus)
        base = top * 0.6 + avg * 0.4
        return max(0.0, min(1.0, base * (1.0 - conflict * 0.55)))


class EnsembleCoordinator:
    def __init__(self) -> None:
        self.family = ThesisFamilyModel()
        self.aggregate = FamilyConfidenceAggregator()
        self.conflict = InterFamilyConflictEngine()
        self.weight_adapter = ThesisWeightAdapter()

    def combine(self, votes: list[ThesisVote]) -> EnsembleDecision:
        consensus = self.aggregate.aggregate(votes)
        conflict = self.conflict.score(consensus)
        confidence = self.weight_adapter.adapt(consensus, conflict)

        score = 0.0
        if consensus:
            for item in consensus:
                sign = 1.0 if item.net_direction == Direction.LONG else -1.0 if item.net_direction == Direction.SHORT else 0.0
                score += sign * item.confidence
            score /= len(consensus)

        if score > 0.08:
            net = Direction.LONG
        elif score < -0.08:
            net = Direction.SHORT
        else:
            net = Direction.FLAT

        return EnsembleDecision(
            net_direction=net,
            confidence=confidence,
            inter_family_conflict=conflict,
            family_consensus=consensus,
        )


__all__ = [
    "EnsembleCoordinator",
    "FamilyConfidenceAggregator",
    "InterFamilyConflictEngine",
    "ThesisFamilyModel",
    "ThesisWeightAdapter",
]
