from __future__ import annotations

from typing import Any, Protocol

from .base import (
    BaseBarsProvider,
    BaseCrossAssetProvider,
    BaseExecutionStatsProvider,
    BaseGammaProvider,
    BaseOrderBookProvider,
    BaseTickProvider,
    ProviderResult,
)


class Provider(Protocol):
    def __call__(self, instrument: str, asof: Any, runtime_context: dict) -> Any: ...


__all__ = [
    "Provider",
    "ProviderResult",
    "BaseBarsProvider",
    "BaseTickProvider",
    "BaseOrderBookProvider",
    "BaseGammaProvider",
    "BaseCrossAssetProvider",
    "BaseExecutionStatsProvider",
]
