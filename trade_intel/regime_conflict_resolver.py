from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RegimeConflictResolution:
    resolved_regime: str
    confidence: float
    conflict_score: float
    reason_codes: list[str]


class RegimeConflictResolver:
    def resolve(self, sources: dict[str, tuple[str, float]]) -> RegimeConflictResolution:
        # sources: source_name -> (regime, confidence)
        if not sources:
            return RegimeConflictResolution("unknown", 0.0, 1.0, ["REGIME_SOURCE_MISSING"])

        votes: dict[str, float] = {}
        for _, (regime, conf) in sources.items():
            votes[regime] = votes.get(regime, 0.0) + max(0.0, min(1.0, conf))

        resolved = max(votes, key=votes.get)
        total = sum(votes.values())
        confidence = 0.0 if total == 0 else votes[resolved] / total
        conflict = 1.0 - confidence

        reasons: list[str] = []
        if conflict > 0.45:
            reasons.append("REGIME_CONFLICT_HIGH")
        if confidence < 0.4:
            reasons.append("REGIME_CONFIDENCE_LOW")

        return RegimeConflictResolution(resolved, confidence, conflict, reasons)
