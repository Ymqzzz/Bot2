from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable

from .pipeline import MarketIntelPipeline


@dataclass(frozen=True)
class ReplayFrame:
    timestamp: str
    instrument: str
    bars: tuple[dict[str, Any], ...] = ()
    ticks: tuple[dict[str, Any], ...] = ()
    provider_payloads: dict[str, Any] | None = None
    provider_statuses: dict[str, Any] | None = None


class MarketIntelReplayer:
    def __init__(self, pipeline: MarketIntelPipeline):
        self.pipeline = pipeline

    @staticmethod
    def _stable_json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def rebuild(self, frames: Iterable[ReplayFrame], config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        config = config or {}
        snapshots: list[dict[str, Any]] = []
        for frame in frames:
            snapshots.append(
                self.pipeline.build_snapshot(
                    timestamp=frame.timestamp,
                    instrument=frame.instrument,
                    bars=[dict(x) for x in frame.bars],
                    ticks=[dict(x) for x in frame.ticks],
                    provider_payloads=dict(frame.provider_payloads or {}),
                    provider_statuses=dict(frame.provider_statuses or {}),
                    config=dict(config),
                )
            )
        return snapshots

    def validate_equal(self, frames: Iterable[ReplayFrame], config: dict[str, Any] | None = None) -> bool:
        first = self.rebuild(frames=frames, config=config)
        second = self.rebuild(frames=frames, config=config)
        return self._stable_json(first) == self._stable_json(second)


def rebuild_snapshots(
    pipeline: MarketIntelPipeline,
    frames: Iterable[ReplayFrame],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return MarketIntelReplayer(pipeline).rebuild(frames=frames, config=config)


def validate_deterministic_replay(
    pipeline: MarketIntelPipeline,
    frames: Iterable[ReplayFrame],
    config: dict[str, Any] | None = None,
) -> bool:
    return MarketIntelReplayer(pipeline).validate_equal(frames=frames, config=config)
from typing import Iterable, List

from .models import MarketIntelSnapshot


class MarketIntelReplay:
    def __init__(self, snapshots: Iterable[MarketIntelSnapshot]) -> None:
        self._snapshots: List[MarketIntelSnapshot] = list(snapshots)

    def iter_snapshots(self) -> Iterable[MarketIntelSnapshot]:
        return iter(self._snapshots)
