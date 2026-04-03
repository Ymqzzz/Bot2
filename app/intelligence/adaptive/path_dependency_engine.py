from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.base import clamp
from app.intelligence.adaptive.adaptive_types import PathDependencyReport
from app.intelligence.adaptive.excursion_profile_tracker import ExcursionProfileTracker
from app.intelligence.adaptive.followthrough_quality_scorer import FollowthroughQualityScorer
from app.intelligence.adaptive.path_conditioned_exit_logic import PathConditionedExitLogic
from app.intelligence.adaptive.trade_path_shape_model import TradePathShapeModel


@dataclass
class PathDependencyEngine:
    shape_model: TradePathShapeModel = TradePathShapeModel()
    excursion_tracker: ExcursionProfileTracker = ExcursionProfileTracker()
    followthrough_scorer: FollowthroughQualityScorer = FollowthroughQualityScorer()
    exit_logic: PathConditionedExitLogic = PathConditionedExitLogic()

    def evaluate(self, *, context: dict) -> PathDependencyReport:
        pnl_path = [float(v) for v in context.get("pnl_path", [])]
        excursion = self.excursion_tracker.summarize(pnl_path)
        smoothness = self.shape_model.smoothness(pnl_path)
        balance = self.shape_model.excursion_balance(excursion["mfe"], excursion["mae"])
        near_invalid = clamp(float(context.get("near_invalidation_ratio", 0.0)))

        followthrough = self.followthrough_scorer.score(
            initial_thrust=float(context.get("initial_thrust", 0.4)),
            sustained_move=float(context.get("sustained_move", 0.4)),
            stop_zone_probes=int(context.get("stop_zone_probes", 0)),
        )
        quality = clamp(smoothness * 0.35 + balance * 0.35 + followthrough * 0.3)
        adjustments = self.exit_logic.adjustments(path_quality=quality, near_invalidation_ratio=near_invalid)

        if quality >= 0.7:
            label = "healthy_trend"
        elif quality >= 0.45:
            label = "fragile_grind"
        else:
            label = "chaotic_path"

        return PathDependencyReport(
            health_label=label,
            path_quality_score=quality,
            confidence_decay=adjustments["confidence_decay"],
            stop_tightening_factor=adjustments["stop_tightening_factor"],
            scale_out_bias=adjustments["scale_out_bias"],
            near_invalidation_ratio=near_invalid,
            followthrough_score=followthrough,
        )
