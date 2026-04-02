from pathlib import Path

from app.ml.config import MLConfig
from app.ml.inference_service import InferenceService
from app.ml.replay_store import ReplayStore
from app.ml.rl_modes import RLMode
from app.ml.state_builder import RLState


class DummyModel:
    def predict_proba(self, X):
        return [[0.1, 0.9, 0, 0, 0, 0, 0, 0]]


def test_inference_fallback_with_low_confidence(tmp_path: Path):
    cfg = MLConfig(min_confidence=0.95, replay_store_path=tmp_path / "replay.jsonl")
    service = InferenceService(cfg, ReplayStore(cfg.replay_store_path))
    state = RLState(values=__import__("numpy").zeros(53), missing_mask=__import__("numpy").zeros(53), metadata={})
    decision = service.infer(
        model=DummyModel(),
        state=state,
        mode=RLMode.SHADOW,
        has_candidate=True,
        in_position=False,
        risk_deterioration=False,
        baseline_action=1,
        ood_score=0.0,
    )
    assert decision.action == 1
    assert decision.gated.accepted is False
