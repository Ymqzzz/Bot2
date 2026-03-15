from __future__ import annotations

from typing import Any

from .pipeline import TradeIntelPipeline


class TradeIntelReplayEngine:
    def __init__(self, pipeline: TradeIntelPipeline):
        self.pipeline = pipeline

    def replay_stepwise(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for s in steps:
            typ = s.get("type")
            if typ == "prepare":
                out.append(self.pipeline.prepare_trade(s["candidate"], s.get("market", {}), s.get("portfolio", {}), s.get("runtime", {})))
            elif typ == "open":
                out.append(self.pipeline.on_trade_open(s["trade_info"], s.get("market", {})))
            elif typ == "update":
                out.append(self.pipeline.on_trade_update(s["trade_info"], s.get("market", {})))
            elif typ == "partial":
                out.append(self.pipeline.on_trade_partial(s["trade_info"], s.get("partial_info", {}), s.get("market", {})))
            elif typ == "close":
                out.append(self.pipeline.on_trade_close(s["trade_info"], s.get("close_info", {}), s.get("market", {})))
            else:
                out.append({"ignored": s})
        return out

    def replay_trade(self, steps: list[dict[str, Any]], trade_id: str) -> list[dict[str, Any]]:
        return [x for x in self.replay_stepwise(steps) if x and x.get("trade_id") == trade_id]
