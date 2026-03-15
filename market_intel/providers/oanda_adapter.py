from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Dict, Optional

import numpy as np
import pandas as pd

from .base import BaseBarsProvider, BaseOrderBookProvider, BaseTickProvider, ProviderResult


class OandaAdapter(BaseBarsProvider, BaseTickProvider, BaseOrderBookProvider):
    """Adapter around existing runtime OANDA helpers (safe_get + caches)."""

    _GRAN_MAP = {
        "M1": "M1",
        "M5": "M5",
        "M15": "M15",
        "M30": "M30",
        "H1": "H1",
        "H4": "H4",
        "D": "D",
        "D1": "D",
    }

    def __init__(
        self,
        *,
        host: str,
        account_id: str,
        safe_get: Callable[..., Optional[dict]],
        price_cache: Optional[Dict[str, float]] = None,
        spread_cache: Optional[Dict[str, float]] = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.account_id = account_id
        self.safe_get = safe_get
        self.price_cache = price_cache if price_cache is not None else {}
        self.spread_cache = spread_cache if spread_cache is not None else {}

    @staticmethod
    def _to_utc(ts: str) -> str:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except Exception:
            return ts

    @staticmethod
    def _float_any(row: dict, keys, default=0.0) -> float:
        for key in keys:
            try:
                if key in row:
                    return float(row.get(key, default))
            except Exception:
                continue
        return float(default)

    def get_bars(self, instrument: str, *, count: int = 500, granularity: str = "M5") -> ProviderResult[pd.DataFrame]:
        g = self._GRAN_MAP.get(granularity.upper(), granularity)
        payload = self.safe_get(
            f"{self.host}/instruments/{instrument}/candles",
            params={"price": "M", "granularity": g, "count": int(count)},
        )
        candles = (payload or {}).get("candles", [])
        if not candles:
            return ProviderResult(ok=False, status="unavailable", source="oanda", error="No candles returned")

        rows = []
        for candle in candles:
            if not candle.get("complete"):
                continue
            mid = candle.get("mid") or {}
            rows.append(
                {
                    "time": self._to_utc(str(candle.get("time", ""))),
                    "o": float(mid.get("o", 0.0)),
                    "h": float(mid.get("h", 0.0)),
                    "l": float(mid.get("l", 0.0)),
                    "c": float(mid.get("c", 0.0)),
                    "v": int(candle.get("volume", 0)),
                }
            )

        if not rows:
            return ProviderResult(ok=False, status="unavailable", source="oanda", error="No complete candles")
        return ProviderResult(ok=True, data=pd.DataFrame(rows), status="ok", source="oanda")

    def get_ticks(self, instrument: str, *, limit: int = 1) -> ProviderResult[list]:
        payload = self.safe_get(
            f"{self.host}/accounts/{self.account_id}/pricing",
            params={"instruments": instrument},
        )
        prices = (payload or {}).get("prices", [])
        if prices:
            p = prices[0]
            bid = float((p.get("bids") or [{}])[0].get("price", 0.0))
            ask = float((p.get("asks") or [{}])[0].get("price", 0.0))
            mid = (bid + ask) / 2.0 if bid and ask else float(self.price_cache.get(instrument, 0.0) or 0.0)
            spread = max(0.0, ask - bid) if bid and ask else float(self.spread_cache.get(instrument, 0.0) or 0.0)
            state = "live"
            out = [{"time": self._to_utc(str(p.get("time", ""))), "bid": bid, "ask": ask, "mid": mid, "spread": spread}]
        else:
            mid = float(self.price_cache.get(instrument, 0.0) or 0.0)
            spread = float(self.spread_cache.get(instrument, 0.0) or 0.0)
            out = [{"time": datetime.now(timezone.utc).isoformat(), "bid": mid - spread / 2.0, "ask": mid + spread / 2.0, "mid": mid, "spread": spread}]
            state = "cache"

        if out[0]["mid"] <= 0:
            return ProviderResult(ok=False, status="unavailable", source="oanda", error="No tick data")
        return ProviderResult(ok=True, data=out[: max(1, limit)], status="ok", source="oanda", meta={"tick_state": state})

    def _positionbook(self, instrument: str) -> dict:
        return self.safe_get(f"{self.host}/instruments/{instrument}/positionBook") or {}

    def _orderbook(self, instrument: str) -> dict:
        return self.safe_get(f"{self.host}/instruments/{instrument}/orderBook") or {}

    def get_orderflow(self, instrument: str, *, price: float, atr_value: float) -> ProviderResult[dict]:
        features = {
            "available": False,
            "positionbook_available": False,
            "orderbook_available": False,
            "pos_skew_norm": 0.0,
            "crowding_strength": 0.0,
            "nearest_wall_above_px": None,
            "nearest_wall_below_px": None,
            "wall_distance_atr_above": None,
            "wall_distance_atr_below": None,
            "wall_strength_above": 0.0,
            "wall_strength_below": 0.0,
            "sl_wall_risk": 0.0,
            "tp_wall_adjusted": False,
            "tp_wall_cut_distance_atr": 0.0,
        }

        pb = self._positionbook(instrument)
        pb_buckets = (pb.get("positionBook") or {}).get("buckets", pb.get("buckets", []))
        longs = [self._float_any(b, ["longCountPercent", "longCount"], 0.0) for b in pb_buckets]
        shorts = [self._float_any(b, ["shortCountPercent", "shortCount"], 0.0) for b in pb_buckets]
        if longs and shorts:
            raw = (sum(longs) - sum(shorts)) / (sum(longs) + sum(shorts) + 1e-9)
            features["positionbook_available"] = True
            features["pos_skew_norm"] = float(max(-1.0, min(1.0, np.tanh(raw * 3.0))))
            features["crowding_strength"] = float(min(1.0, abs(features["pos_skew_norm"])))

        ob = self._orderbook(instrument)
        ob_buckets = (ob.get("orderBook") or {}).get("buckets", ob.get("buckets", []))
        strengths = []
        walls_above = []
        walls_below = []
        for bucket in ob_buckets:
            px = self._float_any(bucket, ["price"], 0.0)
            longp = self._float_any(bucket, ["longCountPercent", "longCount"], 0.0)
            shortp = self._float_any(bucket, ["shortCountPercent", "shortCount"], 0.0)
            orderp = self._float_any(bucket, ["orderCountPercent", "orderCount"], longp + shortp)
            strength = max(orderp, longp + shortp)
            if px <= 0 or strength <= 0:
                continue
            strengths.append(strength)
            if px >= price:
                walls_above.append((px, strength))
            else:
                walls_below.append((px, strength))

        if strengths:
            denom = max(float(np.percentile(strengths, 90)), 1e-9)
            near_above = sorted(walls_above, key=lambda x: abs(x[0] - price))[:5]
            near_below = sorted(walls_below, key=lambda x: abs(x[0] - price))[:5]
            if near_above:
                px, st = near_above[0]
                features["nearest_wall_above_px"] = px
                features["wall_strength_above"] = float(min(2.0, st / denom))
                features["wall_distance_atr_above"] = float(abs(px - price) / max(atr_value, 1e-9))
            if near_below:
                px, st = near_below[0]
                features["nearest_wall_below_px"] = px
                features["wall_strength_below"] = float(min(2.0, st / denom))
                features["wall_distance_atr_below"] = float(abs(price - px) / max(atr_value, 1e-9))
            features["orderbook_available"] = True

        features["available"] = bool(features["positionbook_available"] or features["orderbook_available"])
        if features["positionbook_available"] and features["orderbook_available"]:
            availability = "full"
        elif features["positionbook_available"]:
            availability = "positionbook_only"
        elif features["orderbook_available"]:
            availability = "orderbook_only"
        else:
            availability = "none"

        status = "ok" if features["available"] else "unavailable"
        return ProviderResult(
            ok=features["available"],
            data=features,
            status=status,
            source="oanda",
            meta={"availability_state": availability},
        )

    def get_positioning(self, instrument: str, *, mid_price: float) -> ProviderResult[dict]:
        pb = self._positionbook(instrument)
        ob = self._orderbook(instrument)
        skew = 0.0
        tops = []

        buckets = (pb.get("positionBook") or {}).get("buckets", pb.get("buckets", []))
        longs = [self._float_any(b, ["longCountPercent"], 0.0) for b in buckets]
        shorts = [self._float_any(b, ["shortCountPercent"], 0.0) for b in buckets]
        if longs and shorts:
            skew = (sum(longs) / len(longs) - sum(shorts) / len(shorts)) / 100.0

        ob_buckets = (ob.get("orderBook") or {}).get("buckets", ob.get("buckets", []))
        if ob_buckets:
            def score(row: dict) -> float:
                px = self._float_any(row, ["price"], 0.0)
                return -abs(px - (mid_price if mid_price == mid_price else px))

            tops = sorted(ob_buckets, key=score)[:3]
            tops = [{"price": self._float_any(row, ["price"], 0.0)} for row in tops]

        contrarian = "fade_longs" if skew > 0.15 else "fade_shorts" if skew < -0.15 else "neutral"
        status = "ok" if (buckets or ob_buckets) else "unavailable"
        return ProviderResult(
            ok=status == "ok",
            data={"skew": skew, "top_levels": tops, "contrarian": contrarian},
            status=status,
            source="oanda",
        )
