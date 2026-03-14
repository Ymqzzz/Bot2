from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Generic, Optional, TypeVar


T = TypeVar("T")


@dataclass
class ProviderResult(Generic[T]):
    ok: bool
    data: Optional[T] = None
    status: str = "ok"
    source: str = ""
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    meta: Dict[str, object] = field(default_factory=dict)


class BaseBarsProvider(ABC):
    @abstractmethod
    def get_bars(self, instrument: str, *, count: int = 500, granularity: str = "M5") -> ProviderResult[object]:
        raise NotImplementedError


class BaseTickProvider(ABC):
    @abstractmethod
    def get_ticks(self, instrument: str, *, limit: int = 1) -> ProviderResult[object]:
        raise NotImplementedError


class BaseOrderBookProvider(ABC):
    @abstractmethod
    def get_orderflow(self, instrument: str, *, price: float, atr_value: float) -> ProviderResult[dict]:
        raise NotImplementedError


class BaseGammaProvider(ABC):
    @abstractmethod
    def get_gamma(self, instrument: str) -> ProviderResult[dict]:
        raise NotImplementedError


class BaseCrossAssetProvider(ABC):
    @abstractmethod
    def get_cross_asset_returns(self) -> ProviderResult[dict]:
        raise NotImplementedError


class BaseExecutionStatsProvider(ABC):
    @abstractmethod
    def get_execution_stats(self, *, n: int = 100) -> ProviderResult[dict]:
        raise NotImplementedError
