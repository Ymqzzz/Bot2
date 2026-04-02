from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from app.ml.feature_schema import FEATURE_SPECS, feature_names


@dataclass(frozen=True)
class NormalizationStats:
    version: str
    mean: dict[str, float]
    std: dict[str, float]


@dataclass(frozen=True)
class RLState:
    values: np.ndarray
    missing_mask: np.ndarray
    metadata: dict[str, Any]


class StateBuilder:
    def __init__(self, stats: NormalizationStats):
        self.stats = stats
        self._names = feature_names()

    def build(
        self,
        market_state: dict[str, Any],
        signal_state: dict[str, Any],
        risk_state: dict[str, Any],
        execution_state: dict[str, Any],
        context_state: dict[str, Any],
    ) -> RLState:
        merged = {}
        merged.update(market_state)
        merged.update(signal_state)
        merged.update(risk_state)
        merged.update(execution_state)
        merged.update(context_state)

        values = np.zeros(len(self._names), dtype=np.float32)
        mask = np.zeros(len(self._names), dtype=np.float32)
        for idx, spec in enumerate(FEATURE_SPECS):
            raw = merged.get(spec.name)
            if raw is None:
                mask[idx] = 1.0
                values[idx] = 0.0
                continue
            val = float(raw)
            if math.isnan(val):
                mask[idx] = 1.0
                values[idx] = 0.0
                continue
            mu = self.stats.mean.get(spec.name, 0.0)
            sigma = max(self.stats.std.get(spec.name, 1.0), 1e-6)
            values[idx] = (val - mu) / sigma

        metadata = {
            "stats_version": self.stats.version,
            "feature_names": list(self._names),
            "missing_count": int(mask.sum()),
        }
        return RLState(values=values, missing_mask=mask, metadata=metadata)
