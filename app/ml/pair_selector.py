from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math


@dataclass
class PairLearningState:
    entry_count: int = 0
    avg_result: float = 0.0
    m2_result: float = 0.0
    ewma_sharpe: float = 0.0


@dataclass
class PairModelSignal:
    trade_likelihood: float
    pair_score: float
    expected_result: float
    sharpe_improvement: float


@dataclass
class PairSelectionModel:
    """Small online model that reuses prior entries/results for pair ranking."""

    learning_rate: float = 0.05
    l2_penalty: float = 1e-4
    sharpe_window: int = 50
    _weights: dict[str, float] = field(
        default_factory=lambda: {
            "bias": -0.3,
            "confidence": 0.9,
            "confluence": 0.7,
            "setup_recent_perf": 0.6,
            "instrument_recent_perf": 0.45,
            "spread_penalty": -0.35,
            "volatility_burst": -0.2,
            "previous_entry_quality": 0.5,
            "previous_result": 0.55,
        }
    )
    _pair_state: dict[str, PairLearningState] = field(default_factory=dict)
    _recent_results: deque[float] = field(default_factory=lambda: deque(maxlen=50))

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, x))))

    def _state(self, instrument: str) -> PairLearningState:
        state = self._pair_state.get(instrument)
        if state is None:
            state = PairLearningState()
            self._pair_state[instrument] = state
        return state

    def baseline_sharpe(self) -> float:
        if len(self._recent_results) < 5:
            return 0.0
        mean = sum(self._recent_results) / len(self._recent_results)
        var = sum((x - mean) ** 2 for x in self._recent_results) / max(1, len(self._recent_results) - 1)
        std = math.sqrt(max(var, 1e-9))
        return mean / std

    def build_feature_map(self, instrument: str, payload: dict[str, float]) -> dict[str, float]:
        state = self._state(instrument)
        return {
            "bias": 1.0,
            "confidence": float(payload.get("confidence", 0.0)),
            "confluence": float(payload.get("confluence", 0.0)),
            "setup_recent_perf": float(payload.get("setup_recent_perf", 0.0)),
            "instrument_recent_perf": float(payload.get("instrument_recent_perf", 0.0)),
            "spread_penalty": -abs(float(payload.get("spread_norm", 0.0))),
            "volatility_burst": float(payload.get("volatility_burst", 0.0)),
            "previous_entry_quality": float(payload.get("previous_entry_quality", 0.0)),
            "previous_result": state.avg_result,
        }

    def score(self, instrument: str, payload: dict[str, float]) -> PairModelSignal:
        feats = self.build_feature_map(instrument, payload)
        logit = sum(self._weights.get(k, 0.0) * v for k, v in feats.items())
        likelihood = self._sigmoid(logit)
        state = self._state(instrument)
        expected_result = (0.65 * likelihood + 0.35 * state.avg_result)
        pair_score = max(0.0, min(1.0, 0.55 * likelihood + 0.45 * max(0.0, state.ewma_sharpe)))
        sharpe_improvement = max(-2.0, min(2.0, state.ewma_sharpe - self.baseline_sharpe()))
        return PairModelSignal(
            trade_likelihood=likelihood,
            pair_score=pair_score,
            expected_result=expected_result,
            sharpe_improvement=sharpe_improvement,
        )

    def learn(self, instrument: str, payload: dict[str, float], realized_result: float) -> None:
        signal = self.score(instrument, payload)
        target = 1.0 if realized_result > 0 else 0.0
        err = target - signal.trade_likelihood
        feats = self.build_feature_map(instrument, payload)
        for k, v in feats.items():
            self._weights[k] = self._weights.get(k, 0.0) + self.learning_rate * (err * v - self.l2_penalty * self._weights.get(k, 0.0))

        state = self._state(instrument)
        state.entry_count += 1
        delta = realized_result - state.avg_result
        state.avg_result += delta / max(1, state.entry_count)
        state.m2_result += delta * (realized_result - state.avg_result)
        variance = state.m2_result / max(1, state.entry_count - 1)
        std = math.sqrt(max(variance, 1e-9))
        current_sharpe = state.avg_result / std if state.entry_count > 1 else 0.0
        state.ewma_sharpe = 0.9 * state.ewma_sharpe + 0.1 * current_sharpe
        self._recent_results.append(realized_result)
