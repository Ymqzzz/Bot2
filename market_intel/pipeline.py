from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any, Callable, Dict, List, Mapping, Optional

from .models import MarketIntelSnapshot, ProviderStatus, SessionContext


class MarketIntelPipelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class DependencySpec:
    name: str
    field: str
    provider_key: str
    strict_default: bool = False


class MarketIntelPipeline:
    """Builds a market intelligence snapshot with ordered dependencies."""

    # Ordered according to the integration brief's dependency chain.
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

    def __init__(self, providers: Optional[Mapping[str, Callable[[str, datetime, dict], Any]]] = None) -> None:
        self.providers: Dict[str, Callable[[str, datetime, dict], Any]] = dict(providers or {})

    def build_snapshot(self, instrument: str, asof: datetime, runtime_context: Optional[dict] = None) -> MarketIntelSnapshot:
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
                self._register_failure(
                    state,
                    dep,
                    dep_is_strict,
                    reason="provider_not_configured",
                    raise_on_fail=dep_is_strict,
                )
                continue

            started = perf_counter()
            try:
                result = provider(instrument, asof, runtime_context)
            except Exception as exc:  # noqa: BLE001 - strict/non-strict error policy intentionally broad.
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
            ProviderStatus(
                provider=dep.provider_key,
                ok=False,
                latency_ms=latency_ms,
                reason=reason,
                strict=is_strict,
            )
        )
        if raise_on_fail:
            raise MarketIntelPipelineError(f"Strict dependency '{dep.name}' failed: {reason}")
