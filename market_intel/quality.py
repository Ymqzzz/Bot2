from __future__ import annotations

from typing import Optional

from .models import ExecutionQualitySnapshot


def compute_execution_quality(
    expected_slippage_bps: float,
    fill_probability: float,
    urgency_score: Optional[float] = None,
) -> ExecutionQualitySnapshot:
    return ExecutionQualitySnapshot(
        expected_slippage_bps=expected_slippage_bps,
        fill_probability=fill_probability,
        urgency_score=urgency_score if urgency_score is not None else 1.0 - fill_probability,
    )
