from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app.intelligence.institutional.schemas import DecisionSnapshot, ModelVersion


class ModelRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, ModelVersion] = {}

    def register(
        self,
        *,
        model_name: str,
        version: str,
        training_data_tag: str,
        created_at: datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self._registry[model_name] = ModelVersion(
            model_name=model_name,
            version=version,
            training_data_tag=training_data_tag,
            created_at=created_at or datetime.utcnow(),
            metadata=metadata or {},
        )

    def snapshot(self) -> dict[str, str]:
        return {name: value.version for name, value in self._registry.items()}

    def details(self) -> dict[str, ModelVersion]:
        return dict(self._registry)


class ReproducibilityBundle:
    @staticmethod
    def feature_hash(features: dict[str, float]) -> str:
        ordered = {k: round(float(v), 10) for k, v in sorted(features.items())}
        payload = json.dumps(ordered, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def regime_hash(regime_snapshot: dict[str, Any]) -> str:
        payload = json.dumps(regime_snapshot, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ReasonCodeRegistry:
    def __init__(self) -> None:
        self._reasons: dict[str, str] = {}

    def register(self, code: str, description: str) -> None:
        self._reasons[code] = description

    def describe(self, code: str) -> str:
        return self._reasons.get(code, "unknown_reason")


class DecisionAuditLog:
    def __init__(self) -> None:
        self._items: list[DecisionSnapshot] = []

    def append(
        self,
        *,
        decision_id: str,
        timestamp: datetime,
        trade_id: str,
        model_versions: dict[str, str],
        features: dict[str, float],
        regime_snapshot: dict[str, Any],
        signal_contributors: dict[str, float],
        penalties: dict[str, float],
        overrides: dict[str, str],
        reason_codes: list[str],
        approval_path: list[str],
        approved: bool,
        confidence: float,
    ) -> DecisionSnapshot:
        snap = DecisionSnapshot(
            decision_id=decision_id,
            timestamp=timestamp,
            trade_id=trade_id,
            model_versions=model_versions,
            feature_hash=ReproducibilityBundle.feature_hash(features),
            regime_snapshot=regime_snapshot,
            signal_contributors=signal_contributors,
            penalties=penalties,
            overrides=overrides,
            reason_codes=reason_codes,
            approval_path=approval_path,
            approved=approved,
            confidence=confidence,
        )
        self._items.append(snap)
        return snap

    def latest(self) -> DecisionSnapshot | None:
        if not self._items:
            return None
        return self._items[-1]

    @property
    def items(self) -> list[DecisionSnapshot]:
        return list(self._items)


__all__ = [
    "DecisionAuditLog",
    "ModelRegistry",
    "ReasonCodeRegistry",
    "ReproducibilityBundle",
]
