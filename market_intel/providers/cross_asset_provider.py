from __future__ import annotations

from typing import Dict

from .base import BaseBarsProvider, BaseCrossAssetProvider, ProviderResult


class CrossAssetProvider(BaseCrossAssetProvider):
    def __init__(self, *, bars_provider: BaseBarsProvider, assets: Dict[str, str]) -> None:
        self.bars_provider = bars_provider
        self.assets = assets

    @staticmethod
    def _ret(first: float, last: float) -> float:
        return (last / first - 1.0) if first else 0.0

    def get_cross_asset_returns(self) -> ProviderResult[dict]:
        out = {}
        degraded = False

        for asset_name, instrument in self.assets.items():
            m5 = self.bars_provider.get_bars(instrument, count=13, granularity="M5")
            h1 = self.bars_provider.get_bars(instrument, count=2, granularity="H1")

            entry = {
                "instrument": instrument,
                "ret_5m": None,
                "ret_1h": None,
                "status": "ok",
            }

            if m5.ok and m5.data is not None and len(m5.data) >= 2:
                entry["ret_5m"] = float(self._ret(float(m5.data["c"].iloc[-2]), float(m5.data["c"].iloc[-1])))
            else:
                entry["status"] = "degraded"
                degraded = True

            if h1.ok and h1.data is not None and len(h1.data) >= 2:
                entry["ret_1h"] = float(self._ret(float(h1.data["c"].iloc[-2]), float(h1.data["c"].iloc[-1])))
            else:
                entry["status"] = "degraded"
                degraded = True

            out[asset_name] = entry

        return ProviderResult(
            ok=bool(out),
            data=out,
            status="degraded" if degraded else "ok",
            source="cross_asset_provider",
        )
