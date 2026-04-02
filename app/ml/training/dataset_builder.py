from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetRow:
    timestamp: str
    instrument: str
    state_features: dict[str, float]
    feature_mask: dict[str, bool]
    base_candidate: dict
    outcome: dict
    costs: dict
    regime_label: str


def build_dataset(rows: list[DatasetRow]) -> list[DatasetRow]:
    return sorted(rows, key=lambda r: (r.instrument, r.timestamp))
