from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from .base import BaseGammaProvider, BaseBarsProvider, ProviderResult


class GammaProxyProvider(BaseGammaProvider):
    def __init__(
        self,
        *,
        mode: str,
        bars_provider: Optional[BaseBarsProvider] = None,
        futures_options_fetcher: Optional[Callable[[str], dict]] = None,
    ) -> None:
        self.mode = (mode or "none").lower()
        self.bars_provider = bars_provider
        self.futures_options_fetcher = futures_options_fetcher

    def get_gamma(self, instrument: str) -> ProviderResult[dict]:
        if self.mode == "none":
            return ProviderResult(
                ok=False,
                data={"gamma": 0.0, "label": "none", "is_proxy": False},
                status="unavailable",
                source="gamma_proxy",
            )

        if self.mode == "futures_options" and self.futures_options_fetcher:
            data = self.futures_options_fetcher(instrument) or {}
            gamma = float(data.get("gamma", 0.0) or 0.0)
            return ProviderResult(
                ok=True,
                data={"gamma": gamma, "label": "futures_options", "is_proxy": False},
                status="ok",
                source="futures_options",
            )

        if self.mode == "derived_proxy" and self.bars_provider:
            bars_result = self.bars_provider.get_bars(instrument, count=96, granularity="M5")
            df = bars_result.data
            if not bars_result.ok or df is None or len(df) < 20:
                return ProviderResult(
                    ok=False,
                    data={"gamma": 0.0, "label": "derived_proxy", "is_proxy": True},
                    status="unavailable",
                    source="gamma_proxy",
                    error="Not enough bars",
                )
            rets = np.log(df["c"] / df["c"].shift(1)).dropna()
            vol = float(rets.std(ddof=1)) if len(rets) else 0.0
            gamma_proxy = float(1.0 / max(vol, 1e-6))
            return ProviderResult(
                ok=True,
                data={"gamma": gamma_proxy, "label": "derived_proxy", "is_proxy": True},
                status="proxy",
                source="gamma_proxy",
                meta={"proxy_method": "inverse_realized_vol"},
            )

        return ProviderResult(
            ok=False,
            data={"gamma": 0.0, "label": self.mode, "is_proxy": True},
            status="unavailable",
            source="gamma_proxy",
            error=f"Unsupported mode={self.mode}",
        )
