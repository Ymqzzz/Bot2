from __future__ import annotations

from typing import Any, Callable

from .storage import SnapshotStorage


class MarketIntelPipeline:
    def __init__(
        self,
        storage: SnapshotStorage | None = None,
        feature_builder: Callable[..., dict[str, Any]] | None = None,
        quality_builder: Callable[..., tuple[dict[str, Any], dict[str, Any]]] | None = None,
    ):
        self.storage = storage
        self.feature_builder = feature_builder or self._default_feature_builder
        self.quality_builder = quality_builder or self._default_quality_builder

    @staticmethod
    def _default_feature_builder(bars: list[dict] | None = None, ticks: list[dict] | None = None, **_: Any) -> dict[str, Any]:
        bars = bars or []
        ticks = ticks or []
        close = float(bars[-1].get("close", 0.0)) if bars else 0.0
        volume = float(sum(float(b.get("volume", 0.0) or 0.0) for b in bars)) if bars else 0.0
        tick_count = len(ticks)
        return {
            "bar_count": len(bars),
            "tick_count": tick_count,
            "close": close,
            "volume": volume,
        }

    @staticmethod
    def _default_quality_builder(provider_statuses: dict[str, Any] | None = None, **_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        statuses = provider_statuses or {}
        total = len(statuses)
        healthy = sum(1 for _, payload in statuses.items() if (payload or {}).get("status") in ("ok", "healthy"))
        availability = (healthy / total) if total else 1.0
        summary = {
            "provider_availability": availability,
            "provider_count": total,
            "healthy_provider_count": healthy,
        }
        usability_flags = {
            "sufficient_provider_coverage": availability >= 0.7,
            "is_usable": availability >= 0.5,
        }
        return summary, usability_flags

    def build_snapshot(
        self,
        *,
        timestamp: str,
        instrument: str,
        bars: list[dict] | None = None,
        ticks: list[dict] | None = None,
        provider_payloads: dict[str, Any] | None = None,
        provider_statuses: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider_payloads = provider_payloads or {}
        provider_statuses = provider_statuses or {}
        config = config or {}

        features = self.feature_builder(
            bars=bars,
            ticks=ticks,
            provider_payloads=provider_payloads,
            provider_statuses=provider_statuses,
            config=config,
        )
        summary_scores, usability_flags = self.quality_builder(
            features=features,
            provider_payloads=provider_payloads,
            provider_statuses=provider_statuses,
            config=config,
        )

        snapshot = {
            "timestamp": timestamp,
            "instrument": instrument,
            "features": features,
            "summary_scores": summary_scores,
            "provider_statuses": provider_statuses,
            "usability_flags": usability_flags,
        }

        if self.storage:
            self.storage.persist(
                snapshot=snapshot,
                features=features,
                summary_scores=summary_scores,
                provider_statuses=provider_statuses,
                usability_flags=usability_flags,
            )

        return snapshot
