from __future__ import annotations

from dataclasses import dataclass
import math

from app.intelligence.base import clamp
from app.intelligence.adaptive.adaptive_types import EdgePersistenceReport
from app.intelligence.adaptive.crowding_penalty_model import CrowdingPenaltyModel
from app.intelligence.adaptive.edge_half_life_estimator import EdgeHalfLifeEstimator
from app.intelligence.adaptive.expectancy_decay_tracker import ExpectancyDecayTracker
from app.intelligence.adaptive.setup_saturation_monitor import SetupSaturationMonitor


@dataclass
class EdgePersistenceEngine:
    expectancy_decay: ExpectancyDecayTracker = ExpectancyDecayTracker()
    saturation_monitor: SetupSaturationMonitor = SetupSaturationMonitor()
    crowding_model: CrowdingPenaltyModel = CrowdingPenaltyModel()
    half_life_estimator: EdgeHalfLifeEstimator = EdgeHalfLifeEstimator()

    def evaluate(self, *, context: dict) -> EdgePersistenceReport:
        history = [float(x) for x in context.get("expectancy_history", [0.0])]
        slope = self.expectancy_decay.slope(history)
        decay_rate = max(0.0, -slope)
        half_life = self.half_life_estimator.estimate(decay_rate=decay_rate)
        persistence = clamp(math.exp(-decay_rate * 5.0))
        saturation = self.saturation_monitor.saturation(
            trades_recent=int(context.get("setup_trades_recent", 0)),
            baseline=int(context.get("setup_trade_baseline", 20)),
        )
        crowd_pen = self.crowding_model.penalty(
            crowding_score=float(context.get("crowding_score", 0.2)),
            post_win_streak=int(context.get("post_win_streak", 0)),
        )
        overheating = saturation > 0.85 and slope < 0
        trust = clamp(persistence * (1.0 - crowd_pen * 0.5) * (1.0 - saturation * 0.35))

        return EdgePersistenceReport(
            half_life_bars=half_life,
            persistence_score=persistence,
            expectancy_slope=slope,
            saturation_score=saturation,
            crowding_penalty=crowd_pen,
            overheating_flag=overheating,
            trust_multiplier=trust,
        )
