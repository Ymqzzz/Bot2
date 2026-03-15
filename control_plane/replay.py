from __future__ import annotations

from typing import Any

from .pipeline import ControlPlanePipeline


def replay_cycle(pipeline: ControlPlanePipeline, historical_input: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    payload = dict(historical_input or {})
    payload.update(kwargs)
    return pipeline.run_cycle(**payload).to_flat_dict()
