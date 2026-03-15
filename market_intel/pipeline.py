from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from .models import MarketIntelSnapshot, ProviderStatus, SessionContext
from .storage import SnapshotStorage


class MarketIntelPipelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class DependencySpec:
    name: str
    field: str
    provider_key: str
    strict_default: bool = False


class MarketIntelPipeline:
    """Market intel pipeline supporting both snapshot modes used in the repo/tests."""

    DEPENDENCY_ORDER: List[DependencySpec] = [
        DependencySpec("htf_structure", "htf_structure", "htf_structure"),
        DependencySpec("volume_profile", "volume_profile", "volume_profile"),
        DependencySpec("liquidity_map", "liquidity_map", "liquidity_map"),
        DependencySpec("orderbook_proxy", "orderbook_proxy", "orderbook_proxy"),
        DependencySpec("gamma_proxy", "gamma_proxy", "gamma_proxy"),
        DependencySpec("microstructure", "microstructure", "microstructure"),
        DependencySpec("cross_asset", "cross_asset", "cross_asset"),
        DependencySpec("execution_quality", "execution_quality", "execution_quality"),
        DependencySpec("features", "features", "features"),
    ]

    def __init__(
        self,
        storage: SnapshotStorage | None = None,
        feature_builder: Callable[..., dict[str, Any]] | None = None,
        quality_builder: Callable[..., tuple[dict[str, Any], dict[str, Any]]] | None = None,
        providers: Optional[Mapping[str, Callable[[str, datetime, dict], Any]]] = None,
    ) -> None:
        self.storage = storage
        self.feature_builder = feature_builder or self._default_feature_builder
        self.quality_builder = quality_builder or self._default_quality_builder
        self.providers: Dict[str, Callable[[str, datetime, dict], Any]] = dict(providers or {})

    @staticmethod
    def _default_feature_builder(bars: list[dict] | None = None, ticks: list[dict] | None = None, **_: Any) -> dict[str, Any]:
        bars = bars or []
        ticks = ticks or []
        close = float(bars[-1].get("close", 0.0)) if bars else 0.0
        volume = float(sum(float(b.get("volume", 0.0) or 0.0) for b in bars)) if bars else 0.0
        return {
            "bar_count": len(bars),
            "tick_count": len(ticks),
            "close": close,
            "volume": volume,
        }

    @staticmethod
    def _default_quality_builder(provider_statuses: dict[str, Any] | None = None, **_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        statuses = provider_statuses or {}
        total = len(statuses)
        healthy = sum(1 for _, payload in statuses.items() if (payload or {}).get("status") in ("ok", "healthy"))
        availability = (healthy / total) if total else 1.0
        return (
            {
                "provider_availability": availability,
                "provider_count": total,
                "healthy_provider_count": healthy,
            },
            {
                "sufficient_provider_coverage": availability >= 0.7,
                "is_usable": availability >= 0.5,
            },
        )

    def build_snapshot(self, *args, **kwargs):
        if "timestamp" in kwargs:
            return self._build_storage_snapshot(**kwargs)
        return self._build_provider_snapshot(*args, **kwargs)

    def _build_storage_snapshot(
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

    def _build_provider_snapshot(
        self,
        instrument: str,
        asof: datetime,
        runtime_context: Optional[dict] = None,
    ) -> MarketIntelSnapshot:
        runtime_context = runtime_context or {}
        strict_mode = bool(runtime_context.get("strict_mode", False))
        strict_dependencies = set(runtime_context.get("strict_dependencies", []))

        state: Dict[str, Any] = {
            "session": SessionContext(instrument=instrument, asof=asof),
            "provider_status": [],
            "features": [],
            "metadata": {
                "build_started_at": datetime.utcnow().isoformat(),
                "strict_mode": strict_mode,
            },
        }

        for dep in self.DEPENDENCY_ORDER:
            provider = self.providers.get(dep.provider_key)
            dep_is_strict = strict_mode or dep.strict_default or dep.name in strict_dependencies

            if provider is None:
                self._register_failure(state, dep, dep_is_strict, reason="provider_not_configured", raise_on_fail=dep_is_strict)
                continue

            started = perf_counter()
            try:
                result = provider(instrument, asof, runtime_context)
            except Exception as exc:  # noqa: BLE001
                elapsed_ms = (perf_counter() - started) * 1000.0
                self._register_failure(
                    state,
                    dep,
                    dep_is_strict,
                    reason=f"{type(exc).__name__}: {exc}",
                    latency_ms=elapsed_ms,
                    raise_on_fail=dep_is_strict,
                )
                continue

            elapsed_ms = (perf_counter() - started) * 1000.0
            state[dep.field] = result
            state["provider_status"].append(
                ProviderStatus(provider=dep.provider_key, ok=True, latency_ms=elapsed_ms, strict=dep_is_strict)
            )

        state["metadata"]["build_finished_at"] = datetime.utcnow().isoformat()
        return MarketIntelSnapshot(
            session=state["session"],
            provider_status=state["provider_status"],
            htf_structure=state.get("htf_structure"),
            volume_profile=state.get("volume_profile"),
            liquidity_map=state.get("liquidity_map"),
            orderbook_proxy=state.get("orderbook_proxy"),
            gamma_proxy=state.get("gamma_proxy"),
            microstructure=state.get("microstructure"),
            cross_asset=state.get("cross_asset"),
            execution_quality=state.get("execution_quality"),
            features=state.get("features", []),
            metadata=state["metadata"],
        )

    def _register_failure(
        self,
        state: Dict[str, Any],
        dep: DependencySpec,
        is_strict: bool,
        reason: str,
        latency_ms: Optional[float] = None,
        raise_on_fail: bool = False,
    ) -> None:
        state[dep.field] = [] if dep.field == "features" else None
        state["provider_status"].append(
            ProviderStatus(provider=dep.provider_key, ok=False, latency_ms=latency_ms, reason=reason, strict=is_strict)
        )
        if raise_on_fail:
            raise MarketIntelPipelineError(f"Strict dependency '{dep.name}' failed: {reason}")
