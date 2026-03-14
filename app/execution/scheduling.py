from __future__ import annotations

from execution_engine import clip_staging_plan


def build_clip_plan(units: int, liquidity_factor: float, has_near_event: bool) -> list[int]:
    return clip_staging_plan(units=units, liquidity_factor=liquidity_factor, has_near_event=has_near_event)
