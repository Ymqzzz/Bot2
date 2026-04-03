from __future__ import annotations

from collections import deque
from statistics import mean
from typing import Iterable

from app.intelligence.institutional.schemas import AlertEvent, HealthState, OpsSnapshot, TelemetryEvent


class RuntimeMetricsStore:
    def __init__(self, max_events: int = 1_000) -> None:
        self._events: deque[TelemetryEvent] = deque(maxlen=max_events)

    def add(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def all(self) -> list[TelemetryEvent]:
        return list(self._events)

    def by_source(self, source: str) -> list[TelemetryEvent]:
        return [e for e in self._events if e.source == source]


class AlertRouter:
    def __init__(self) -> None:
        self._alerts: list[AlertEvent] = []

    def route(self, alerts: Iterable[AlertEvent]) -> None:
        self._alerts.extend(alerts)

    @property
    def alerts(self) -> list[AlertEvent]:
        return list(self._alerts)


class TelemetryBus:
    def __init__(self) -> None:
        self.metrics = RuntimeMetricsStore()
        self.router = AlertRouter()

    def emit(self, event: TelemetryEvent) -> None:
        self.metrics.add(event)
        alerts = self._derive_alerts(event)
        if alerts:
            self.router.route(alerts)

    def _derive_alerts(self, event: TelemetryEvent) -> list[AlertEvent]:
        alerts: list[AlertEvent] = []
        if event.health == HealthState.DOWN:
            alerts.append(
                AlertEvent(
                    alert_id=f"{event.source}:{event.heartbeat_ts.timestamp()}:down",
                    source=event.source,
                    severity="critical",
                    message="engine_down",
                    created_at=event.heartbeat_ts,
                    payload=event.payload,
                )
            )
        elif event.health == HealthState.DEGRADED and event.confidence < 0.25:
            alerts.append(
                AlertEvent(
                    alert_id=f"{event.source}:{event.heartbeat_ts.timestamp()}:degraded",
                    source=event.source,
                    severity="warning",
                    message="engine_degraded_low_confidence",
                    created_at=event.heartbeat_ts,
                    payload=event.payload,
                )
            )

        if event.latency_ms > 100.0:
            alerts.append(
                AlertEvent(
                    alert_id=f"{event.source}:{event.heartbeat_ts.timestamp()}:latency",
                    source=event.source,
                    severity="warning",
                    message="engine_latency_high",
                    created_at=event.heartbeat_ts,
                    payload={"latency_ms": event.latency_ms, **event.payload},
                )
            )
        return alerts


class SystemStatusAggregator:
    def build(self, events: list[TelemetryEvent], alerts: list[AlertEvent]) -> OpsSnapshot:
        if not events:
            from datetime import datetime

            return OpsSnapshot(
                generated_at=datetime.utcnow(),
                health_ratio=0.0,
                avg_confidence=0.0,
                avg_latency_ms=0.0,
                degraded_sources=["all"],
                active_alerts=alerts,
            )

        healthy = [e for e in events if e.health == HealthState.HEALTHY]
        health_ratio = len(healthy) / len(events)
        avg_confidence = mean(e.confidence for e in events)
        avg_latency = mean(e.latency_ms for e in events)
        degraded = sorted({e.source for e in events if e.health != HealthState.HEALTHY})

        from datetime import datetime

        return OpsSnapshot(
            generated_at=datetime.utcnow(),
            health_ratio=health_ratio,
            avg_confidence=avg_confidence,
            avg_latency_ms=avg_latency,
            degraded_sources=degraded,
            active_alerts=alerts,
        )


class OpsSnapshotBuilder:
    def __init__(self, telemetry: TelemetryBus) -> None:
        self.telemetry = telemetry
        self.aggregator = SystemStatusAggregator()

    def build(self) -> OpsSnapshot:
        events = self.telemetry.metrics.all()
        alerts = self.telemetry.router.alerts
        return self.aggregator.build(events, alerts)


__all__ = [
    "AlertRouter",
    "OpsSnapshotBuilder",
    "RuntimeMetricsStore",
    "SystemStatusAggregator",
    "TelemetryBus",
]
