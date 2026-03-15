from __future__ import annotations

from app.intelligence.base import EngineInput, clamp
from app.intelligence.models import EventRiskState, Evidence


class EventRiskEngine:
    def compute(self, data: EngineInput) -> EventRiskState:
        ctx = data.context
        minutes_to = float(ctx.get("minutes_to_event", 9999.0))
        minutes_since = float(ctx.get("minutes_since_event", 9999.0))
        severity = clamp(float(ctx.get("event_severity", 0.0)))
        relevance = clamp(float(ctx.get("event_relevance", 0.0)))
        spread_stress = clamp(float(data.features.get("spread_percentile", 0.2)))

        pre_window = clamp((90.0 - minutes_to) / 90.0) if minutes_to <= 90 else 0.0
        post_window = clamp((45.0 - minutes_since) / 45.0) if minutes_since <= 45 else 0.0
        contamination = clamp(0.5 * severity * relevance + 0.25 * pre_window + 0.25 * post_window)
        instability = clamp(0.6 * post_window + 0.4 * spread_stress)
        suppress = pre_window > 0.45 and severity > 0.55

        if severity == 0:
            label = "no_event"
        elif suppress:
            label = "pre_event_risk"
        elif post_window > 0.2:
            label = "post_event_instability"
        elif contamination > 0.3:
            label = "event_cooldown"
        else:
            label = "event_background"

        rationale = [
            Evidence("severity", 0.35, severity, "calendar severity"),
            Evidence("relevance", 0.25, relevance, "instrument-event mapping"),
            Evidence("proximity", 0.4, max(pre_window, post_window), "time proximity effect"),
        ]
        return EventRiskState(
            timestamp=data.timestamp,
            instrument=data.instrument,
            trace_id=data.trace_id,
            confidence=clamp(0.4 + contamination),
            sources=["event_feed", "features"],
            rationale=rationale,
            event_label=label,
            severity_score=severity,
            contamination_score=contamination,
            pre_event_suppression=suppress,
            post_event_instability=instability,
            cooldown_state="active" if contamination > 0.3 else "inactive",
        )
