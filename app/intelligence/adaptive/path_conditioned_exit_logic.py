from __future__ import annotations

from app.intelligence.base import clamp


class PathConditionedExitLogic:
    def adjustments(self, *, path_quality: float, near_invalidation_ratio: float) -> dict[str, float]:
        confidence_decay = clamp((1.0 - path_quality) * 0.75 + near_invalidation_ratio * 0.25)
        stop_tightening = clamp((1.0 - path_quality) * 0.6 + near_invalidation_ratio * 0.4)
        scale_out = clamp((1.0 - path_quality) * 0.5 + confidence_decay * 0.5)
        return {
            "confidence_decay": confidence_decay,
            "stop_tightening_factor": stop_tightening,
            "scale_out_bias": scale_out,
        }
