from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QueueEstimate:
    queue_decay: float
    expected_wait_ms: int


class QueuePositionTracker:
    def estimate(self, volatility_score: float, depth_thin: bool, order_type: str) -> QueueEstimate:
        vol = max(0.0, min(1.0, volatility_score))
        base_decay = 0.2 + vol * 0.5
        if depth_thin:
            base_decay += 0.15
        if order_type == "POST_ONLY":
            base_decay += 0.10
        decay = max(0.0, min(1.0, base_decay))
        wait = int(50 + decay * 450)
        return QueueEstimate(queue_decay=decay, expected_wait_ms=wait)
