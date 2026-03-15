from .base import (
    BaseBarsProvider,
    BaseCrossAssetProvider,
    BaseExecutionStatsProvider,
    BaseGammaProvider,
    BaseOrderBookProvider,
    BaseTickProvider,
    ProviderResult,
)

__all__ = [
    "ProviderResult",
    "BaseBarsProvider",
    "BaseTickProvider",
    "BaseOrderBookProvider",
    "BaseGammaProvider",
    "BaseCrossAssetProvider",
    "BaseExecutionStatsProvider",
]
"""Provider interfaces for market intel dependencies."""

from __future__ import annotations

from typing import Any, Protocol


class Provider(Protocol):
    def __call__(self, instrument: str, asof: Any, runtime_context: dict) -> Any: ...
