from __future__ import annotations


class SandboxPromotionPolicy:
    def evaluate(self, *, score: float, min_samples: int, stability: float) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if score < 0.62:
            reasons.append("score_below_threshold")
        if min_samples < 30:
            reasons.append("insufficient_samples")
        if stability < 0.6:
            reasons.append("stability_too_low")
        return not reasons, reasons or ["ready_for_controlled_promotion"]
