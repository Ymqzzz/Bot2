from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("trade_intel")


class TradeIntelEventEmitter:
    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        logger.info("[TRADE_INTEL] %s %s", event_type, payload)

    def sizing_reduced(self, payload: dict[str, Any]) -> None: self.emit("sizing_reduced", payload)
    def sizing_increased(self, payload: dict[str, Any]) -> None: self.emit("sizing_increased", payload)
    def trade_blocked_by_edge_health(self, payload: dict[str, Any]) -> None: self.emit("trade_blocked_by_edge_health", payload)
    def trade_blocked_by_low_intel(self, payload: dict[str, Any]) -> None: self.emit("trade_blocked_by_low_intel", payload)
    def break_even_armed(self, payload: dict[str, Any]) -> None: self.emit("break_even_armed", payload)
    def trailing_armed(self, payload: dict[str, Any]) -> None: self.emit("trailing_armed", payload)
    def partial_taken(self, payload: dict[str, Any]) -> None: self.emit("partial_taken", payload)
    def forced_exit_by_regime_invalidation(self, payload: dict[str, Any]) -> None: self.emit("forced_exit_by_regime_invalidation", payload)
    def forced_exit_by_execution_dislocation(self, payload: dict[str, Any]) -> None: self.emit("forced_exit_by_execution_dislocation", payload)
    def trade_finalized(self, payload: dict[str, Any]) -> None: self.emit("trade_finalized", payload)
    def edge_state_degraded(self, payload: dict[str, Any]) -> None: self.emit("edge_state_degraded", payload)
    def strategy_disabled(self, payload: dict[str, Any]) -> None: self.emit("strategy_disabled", payload)
    def strategy_reenabled(self, payload: dict[str, Any]) -> None: self.emit("strategy_reenabled", payload)
    def decision_declined(self, payload: dict[str, Any]) -> None: self.emit("decision_declined", payload)
    def decision_degraded_approved(self, payload: dict[str, Any]) -> None: self.emit("decision_degraded_approved", payload)
    def health_degraded(self, payload: dict[str, Any]) -> None: self.emit("health_degraded", payload)
