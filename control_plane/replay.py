from __future__ import annotations

from typing import Any

from .pipeline import ControlPlanePipeline


def replay_cycle(pipeline: ControlPlanePipeline, historical_input: dict[str, Any]) -> dict[str, Any]:
    snap = pipeline.run_cycle(**historical_input)
    return snap.to_flat_dict()
