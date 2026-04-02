import pickle
from pathlib import Path

import pytest

from app.ml.feature_schema import schema_hash
from app.ml.model_loader import ModelCompatibilityError, ModelLoader
from app.ml.model_registry import ModelRecord


def test_model_schema_compatibility_check(tmp_path: Path):
    model_path = tmp_path / "model.pkl"
    with model_path.open("wb") as fh:
        pickle.dump({"ok": True}, fh)
    record = ModelRecord(
        model_id="m1",
        model_path=str(model_path),
        training_config={},
        feature_schema_hash=schema_hash(),
        normalization_stats_version="v1",
        windows={},
        performance={},
        created_at="2026-01-01T00:00:00+00:00",
        code_commit_hash="abc",
        reward_version="r1",
        backtest_report="none",
        approved=True,
    )
    loaded = ModelLoader().load(record, expected_stats_version="v1")
    assert loaded.model_id == "m1"

    bad = ModelRecord(**{**record.__dict__, "feature_schema_hash": "bad"})
    with pytest.raises(ModelCompatibilityError):
        ModelLoader().load(bad, expected_stats_version="v1")
