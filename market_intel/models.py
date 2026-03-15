from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    ok: bool
    latency_ms: Optional[float] = None
    reason: Optional[str] = None
    strict: bool = False


@dataclass(frozen=True)
class FeatureValue:
    name: str
    value: float
    source: str
    timestamp: datetime


@dataclass(frozen=True)
class SessionContext:
    instrument: str
    asof: datetime
    timezone: str = "UTC"
    session_label: Optional[str] = None


@dataclass(frozen=True)
class HTFStructure:
    trend: str
    regime: str
    confidence: float
    levels: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class VolumeProfileSnapshot:
    poc: float
    vah: float
    val: float
    hvn: List[float] = field(default_factory=list)
    lvn: List[float] = field(default_factory=list)


@dataclass(frozen=True)
class LiquidityMap:
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    sweep_risk: float = 0.0


@dataclass(frozen=True)
class OrderBookProxySnapshot:
    bid_imbalance: float
    ask_imbalance: float
    spread_bps: float
    depth_score: float


@dataclass(frozen=True)
class GammaProxySnapshot:
    gamma_pressure: float
    gamma_flip: Optional[float] = None
    dealer_positioning: Optional[str] = None


@dataclass(frozen=True)
class MicrostructureSnapshot:
    realized_volatility: float
    microprice_bias: float
    toxicity_score: float


@dataclass(frozen=True)
class CrossAssetContext:
    dxy_beta: Optional[float] = None
    rates_beta: Optional[float] = None
    risk_on_score: Optional[float] = None
    correlations: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionQualitySnapshot:
    expected_slippage_bps: float
    fill_probability: float
    urgency_score: float


@dataclass(frozen=True)
class MarketIntelSnapshot:
    session: SessionContext
    provider_status: List[ProviderStatus] = field(default_factory=list)
    htf_structure: Optional[HTFStructure] = None
    volume_profile: Optional[VolumeProfileSnapshot] = None
    liquidity_map: Optional[LiquidityMap] = None
    orderbook_proxy: Optional[OrderBookProxySnapshot] = None
    gamma_proxy: Optional[GammaProxySnapshot] = None
    microstructure: Optional[MicrostructureSnapshot] = None
    cross_asset: Optional[CrossAssetContext] = None
    execution_quality: Optional[ExecutionQualitySnapshot] = None
    features: List[FeatureValue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_flat_dict(self) -> Dict[str, Any]:
        """Flatten snapshot state for logging/model-input compatibility."""

        def flatten(value: Any, prefix: str, out: Dict[str, Any]) -> None:
            if is_dataclass(value):
                flatten(asdict(value), prefix, out)
                return
            if isinstance(value, datetime):
                out[prefix] = value.isoformat()
                return
            if isinstance(value, Mapping):
                for key, item in value.items():
                    nested = f"{prefix}.{key}" if prefix else str(key)
                    flatten(item, nested, out)
                return
            if isinstance(value, list):
                if not value:
                    out[prefix] = []
                    return
                if all(not isinstance(i, (dict, list)) and not is_dataclass(i) for i in value):
                    out[prefix] = value
                    return
                for idx, item in enumerate(value):
                    nested = f"{prefix}.{idx}" if prefix else str(idx)
                    flatten(item, nested, out)
                return
            out[prefix] = value

        output: Dict[str, Any] = {}
        flatten(self, "", output)
        return {k.lstrip("."): v for k, v in output.items() if k}
