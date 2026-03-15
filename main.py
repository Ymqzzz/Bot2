from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.runtime.adapters import (
    ControlPlaneLifecycleAdapter,
    ResearchCoreLifecycleAdapter,
    TradeIntelLifecycleAdapter,
)
from app.runtime.engine import JsonlEventAuditStore, RuntimeCoordinator, RuntimeCycleInput, RuntimeSnapshot


class RuntimeBootstrap:
    """Thin runtime bootstrap wrapper.

    Responsibilities:
    - load module configs
    - wire provider/pipeline dependencies
    - delegate orchestration to RuntimeCoordinator
    """

    def __init__(self) -> None:
        from control_plane import ControlPlanePipeline, load_config as load_control_plane_config
        from trade_intel import build_default_pipeline, load_config as load_trade_intel_config
        from research_core import ResearchCorePipeline, load_config as load_research_core_config

        control_plane_pipeline = ControlPlanePipeline(load_control_plane_config())
        trade_intel_pipeline = build_default_pipeline(load_trade_intel_config())

        research_cfg = load_research_core_config()
        research_pipeline = None
        if research_cfg.RESEARCH_CORE_ENABLED:
            def _empty_loader(*_args, **_kwargs):
                raise RuntimeError("Replay loader is not available in runtime bootstrap")

            research_pipeline = ResearchCorePipeline(research_cfg, replay_loader=_empty_loader)

        self.coordinator = RuntimeCoordinator(
            control_plane=ControlPlaneLifecycleAdapter(control_plane_pipeline),
            trade_intel=TradeIntelLifecycleAdapter(trade_intel_pipeline),
            research_core=ResearchCoreLifecycleAdapter(research_pipeline),
            store=JsonlEventAuditStore(self._persist_cycle_event),
        )

    def _persist_cycle_event(self, payload: dict[str, Any]) -> None:
        _ = payload

    def run_cycle(
        self,
        instruments: list[str],
        market_data: dict[str, Any],
        bars: dict[str, Any],
        open_positions: list[dict[str, Any]],
        candidate_pool: list[dict[str, Any]],
        snapshot: RuntimeSnapshot | None = None,
        context: dict[str, Any] | None = None,
    ):
        runtime_snapshot = snapshot or RuntimeSnapshot(timestamp=datetime.now(timezone.utc))
        runtime_input = RuntimeCycleInput(
            instruments=instruments,
            market_data=market_data,
            bars=bars,
            open_positions=open_positions,
            context={"candidate_pool": candidate_pool, **(context or {})},
        )
        return self.coordinator.run_cycle(runtime_input, runtime_snapshot)


def build_runtime() -> RuntimeBootstrap:
    return RuntimeBootstrap()
