from __future__ import annotations

from dataclasses import dataclass
import pickle

from app.ml.feature_schema import schema_hash
from app.ml.model_registry import ModelRecord


@dataclass(frozen=True)
class LoadedModel:
    model_id: str
    model: object
    metadata: ModelRecord


class ModelCompatibilityError(RuntimeError):
    pass


class ModelLoader:
    def load(self, record: ModelRecord, expected_stats_version: str) -> LoadedModel:
        if record.feature_schema_hash != schema_hash():
            raise ModelCompatibilityError("feature schema hash mismatch")
        if record.normalization_stats_version != expected_stats_version:
            raise ModelCompatibilityError("normalization stats version mismatch")
        if not record.approved:
            raise ModelCompatibilityError("model not governance-approved")
        with open(record.model_path, "rb") as fh:
            model = pickle.load(fh)
        return LoadedModel(model_id=record.model_id, model=model, metadata=record)
