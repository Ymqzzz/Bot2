from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    reason: str
    confidence: float
    entropy: float


def entropy_from_probs(probs: list[float]) -> float:
    clamped = [max(min(p, 1.0), 1e-12) for p in probs]
    return -sum(p * math.log(p) for p in clamped)


def evaluate_confidence(
    probs: list[float],
    min_confidence: float,
    max_entropy: float,
    disagreement: float,
    ood_score: float,
    allow_ood_influence: bool,
) -> GateDecision:
    confidence = max(probs) if probs else 0.0
    entropy = entropy_from_probs(probs) if probs else float("inf")
    if ood_score > 0.8 and not allow_ood_influence:
        return GateDecision(False, "ood_state", confidence, entropy)
    if confidence < min_confidence:
        return GateDecision(False, "low_confidence", confidence, entropy)
    if entropy > max_entropy:
        return GateDecision(False, "high_entropy", confidence, entropy)
    if disagreement > 0.8 and confidence < min_confidence + 0.1:
        return GateDecision(False, "high_disagreement", confidence, entropy)
    return GateDecision(True, "accepted", confidence, entropy)
