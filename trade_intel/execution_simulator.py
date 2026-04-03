from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adverse_selection_guard import toxicity_penalty
from .child_order_scheduler import schedule_child_orders
from .fill_probability_model import FillProbabilityModel
from .queue_position_tracker import QueuePositionTracker
from .slippage_estimator import SlippageEstimator


@dataclass(slots=True)
class ExecutionEstimate:
    spread_cost: float
    slippage_cost: float
    toxicity_penalty: float
    fill_probability: float
    queue_decay: float
    execution_quality: float
    preferred_order_type: str


class ExecutionSimulator:
    def __init__(self):
        self.fill_model = FillProbabilityModel()
        self.slippage_model = SlippageEstimator()
        self.queue_tracker = QueuePositionTracker()

    def estimate(self, candidate: dict[str, Any], market_context: dict[str, Any]) -> ExecutionEstimate:
        spread_bps = max(0.0, float(market_context.get("spread_bps", 1.0)))
        vol = max(0.0, min(1.0, float(market_context.get("volatility_score", 0.4))))
        latency = max(0.0, min(1.0, float(market_context.get("latency_risk", 0.2))))
        imbalance = max(0.0, min(1.0, float(market_context.get("imbalance_score", 0.3))))
        order_type = str(candidate.get("order_type", "MARKET"))

        spread_cost = spread_bps * 0.01
        slippage_cost = self.slippage_model.estimate(volatility_score=vol, imbalance_score=imbalance, size_fraction=float(candidate.get("size_fraction", 0.2)))
        tox_penalty = toxicity_penalty(float(market_context.get("taker_imbalance", 0.0)), float(market_context.get("short_horizon_drift", 0.0)))

        fill_probability = self.fill_model.estimate(spread_bps, vol, latency, order_type)
        queue = self.queue_tracker.estimate(volatility_score=vol, depth_thin=bool(market_context.get("depth_thin", False)), order_type=order_type)
        queue_decay = queue.queue_decay
        execution_quality = max(0.0, min(1.0, fill_probability - (spread_cost + slippage_cost + tox_penalty)))

        if execution_quality > 0.70 and spread_bps < 1.2:
            order_type = "LIMIT"
        elif execution_quality < 0.35:
            order_type = "POST_ONLY"
        else:
            order_type = str(candidate.get("order_type", "MARKET"))
        # Store proposed schedule for upstream telemetry; runtime can ignore it.
        candidate["child_order_schedule"] = schedule_child_orders(float(candidate.get("order_qty", 1.0)), int(candidate.get("child_slices", 1)), str(candidate.get("urgency", "normal")))

        return ExecutionEstimate(
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
            toxicity_penalty=tox_penalty,
            fill_probability=fill_probability,
            queue_decay=queue_decay,
            execution_quality=execution_quality,
            preferred_order_type=order_type,
        )
