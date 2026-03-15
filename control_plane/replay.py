from __future__ import annotations

from .pipeline import ControlPlanePipeline


def replay_cycle(pipeline: ControlPlanePipeline, **kwargs):
    return pipeline.run_cycle(**kwargs).to_flat_dict()
