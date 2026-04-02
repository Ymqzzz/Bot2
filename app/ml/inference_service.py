from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np

from app.ml.action_space import ensure_valid, valid_actions
from app.ml.config import MLConfig
from app.ml.governance.confidence_gate import GateDecision, evaluate_confidence
from app.ml.governance.policy_guardrails import apply_policy_constraints
from app.ml.replay_store import ReplayStore
from app.ml.rl_modes import RLMode
from app.ml.state_builder import RLState


@dataclass(frozen=True)
class InferenceDecision:
    action: int
    gated: GateDecision
    probs: list[float]
    latency_ms: float


class InferenceService:
    def __init__(self, config: MLConfig, replay_store: ReplayStore):
        self.config = config
        self.replay_store = replay_store

    def _predict_probs(self, model: object, state: RLState) -> list[float]:
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(state.values.reshape(1, -1))[0]
            return [float(p) for p in probs]
        if hasattr(model, "policy") and hasattr(model.policy, "predict"):
            action, _ = model.predict(state.values, deterministic=False)
            out = [0.0] * 8
            out[int(action)] = 1.0
            return out
        return [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def infer(
        self,
        model: object,
        state: RLState,
        mode: RLMode,
        has_candidate: bool,
        in_position: bool,
        risk_deterioration: bool,
        baseline_action: int,
        ood_score: float,
    ) -> InferenceDecision:
        started = time.perf_counter()
        probs = self._predict_probs(model, state)
        raw_action = int(np.argmax(probs))
        mask = valid_actions(has_candidate=has_candidate, in_position=in_position, risk_deterioration=risk_deterioration)
        action = ensure_valid(raw_action, mask)
        disagreement = 0.0 if action == baseline_action else 1.0
        gate = evaluate_confidence(
            probs=probs,
            min_confidence=self.config.min_confidence,
            max_entropy=self.config.max_entropy,
            disagreement=disagreement,
            ood_score=ood_score,
            allow_ood_influence=self.config.allow_ood_influence,
        )
        if not gate.accepted:
            action = baseline_action
        action = apply_policy_constraints(action, mode=mode, hard_risk_blocked=False)
        latency_ms = (time.perf_counter() - started) * 1000.0
        self.replay_store.append(
            {
                "action": action,
                "baseline_action": baseline_action,
                "confidence": gate.confidence,
                "entropy": gate.entropy,
                "gated_reason": gate.reason,
                "latency_ms": latency_ms,
                "missing_count": state.metadata.get("missing_count", 0),
            }
        )
        return InferenceDecision(action=action, gated=gate, probs=probs, latency_ms=latency_ms)
