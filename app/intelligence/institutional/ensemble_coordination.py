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
    _AREA_SPECIALTIES: dict[str, str] = {
        "trend_following": "directional continuation and pullback entries",
        "mean_reversion": "exhaustion fades back toward value",
        "liquidity_sweep": "stop-hunt reclaims and liquidity trap reversals",
        "breakout_continuation": "range expansion and momentum follow-through",
        "event_reaction": "macro catalyst repricing and post-news dislocations",
        "volatility_expansion": "volatility regime expansion and dispersion bursts",
        "other": "cross-regime tactical opportunism",
    }

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

    def specialty_of(self, family: str) -> str:
        return self._AREA_SPECIALTIES.get(family, self._AREA_SPECIALTIES["other"])


class FamilyConfidenceAggregator:
    def __init__(self) -> None:
        self._family_model = ThesisFamilyModel()

    def aggregate(self, votes: list[ThesisVote]) -> list[FamilyConsensus]:
        grouped: dict[str, list[ThesisVote]] = defaultdict(list)
        for vote in votes:
            grouped[vote.thesis_family].append(vote)

        out: list[FamilyConsensus] = []
        for family, family_votes in grouped.items():
            if not family_votes:
                continue
            scores: list[float] = []
            strengths: list[float] = []
            for v in family_votes:
                sign = 1.0 if v.direction == Direction.LONG else -1.0 if v.direction == Direction.SHORT else 0.0
                effective_weight = max(0.05, v.weight) * max(0.05, v.confidence)
                scores.append(sign * effective_weight)
                strengths.append(effective_weight)

            total_strength = sum(strengths)
            if total_strength <= 1e-12:
                continue
            net = sum(scores) / total_strength
            abs_conf = sum(abs(s) for s in scores) / total_strength
            disagreement = sum(abs(s - net) for s in scores) / total_strength
            participation_efficiency = min(1.0, total_strength / len(family_votes))
            if net > 0.12:
                direction = Direction.LONG
            elif net < -0.12:
                direction = Direction.SHORT
            else:
                direction = Direction.FLAT
            conf = max(0.0, min(1.0, abs_conf * (1.0 - min(1.0, disagreement)) * (0.65 + 0.35 * participation_efficiency)))

            out.append(
                FamilyConsensus(
                    thesis_family=family,
                    net_direction=direction,
                    confidence=conf,
                    disagreement=min(1.0, disagreement),
                    voters=len(family_votes),
                    area_specialty=self._family_model.specialty_of(family),
                )
            )

        out.sort(key=lambda x: x.confidence, reverse=True)
        return out


class InterFamilyConflictEngine:
    def score(self, family_consensus: list[FamilyConsensus]) -> float:
        if not family_consensus:
            return 1.0

        values: list[float] = []
        weights: list[float] = []
        for fc in family_consensus:
            sign = 1.0 if fc.net_direction == Direction.LONG else -1.0 if fc.net_direction == Direction.SHORT else 0.0
            values.append(sign * fc.confidence)
            weights.append(max(1.0, float(fc.voters)) * max(0.1, fc.confidence))

        if len(values) == 1:
            return 0.0

        total_w = sum(weights)
        avg = sum(v * w for v, w in zip(values, weights)) / max(1e-12, total_w)
        spread = sum(abs(v - avg) * w for v, w in zip(values, weights)) / max(1e-12, total_w)
        flat_ratio = sum(1 for v in values if abs(v) < 0.08) / len(values)
        return max(0.0, min(1.0, spread * 1.35 + flat_ratio * 0.25))


class ThesisWeightAdapter:
    def adapt(self, family_consensus: list[FamilyConsensus], conflict: float) -> float:
        if not family_consensus:
            return 0.0
        top = family_consensus[0].confidence
        avg = mean(f.confidence for f in family_consensus)
        dominance = max(0.0, top - avg)
        participation = min(1.0, mean(min(1.0, f.voters / 3.0) for f in family_consensus))
        base = top * 0.55 + avg * 0.35 + dominance * 0.10
        return max(0.0, min(1.0, base * (1.0 - conflict * 0.55) * (0.75 + 0.25 * participation)))


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
