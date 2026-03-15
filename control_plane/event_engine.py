from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import ControlPlaneConfig
from .event_calendar import NormalizedEvent, normalize_events
from .event_policies import EVENT_PHASE_POLICIES, EVENT_TYPE_OVERRIDES
from .models import EventDecision
from .reason_codes import (
    EVENT_CALENDAR_UNAVAILABLE,
    EVENT_HIGH_IMPACT_ACTIVE,
    EVENT_NORMAL,
    EVENT_POST_DIGESTION,
    EVENT_POWELL_HEADLINE_RISK,
    EVENT_PRE_LOCKOUT,
    EVENT_RECENT_HIGH_IMPACT,
    EVENT_REVERSION_BLOCKED,
    EVENT_SPREAD_NOT_NORMALIZED,
)


class EventEngine:
    def __init__(self, config: ControlPlaneConfig | None = None, calendar_provider=None) -> None:
        self.config = config or ControlPlaneConfig()
        self.calendar_provider = calendar_provider or (lambda: [])
        self._events: list[NormalizedEvent] = []

    def set_calendar_events(self, raw_events: list[dict[str, Any]]) -> None:
        self._events = normalize_events(raw_events)

    def _load_events(self) -> list[NormalizedEvent]:
        if self._events:
            return self._events
        if not self.config.EVENT_CALENDAR_ENABLED:
            return []
        try:
            return normalize_events(self.calendar_provider() or [])
        except Exception:
            return []

    def get_relevant_events(self, instrument: str, asof: datetime, events: list[NormalizedEvent]) -> list[NormalizedEvent]:
        base, quote = instrument.split("_") if "_" in instrument else (instrument[:3], instrument[3:])
        return [e for e in events if e.currency in {base, quote, "USD"} and abs((e.scheduled_ts - asof).total_seconds()) <= 6 * 3600]

    def classify_event_phase(self, asof: datetime, event: NormalizedEvent) -> str:
        delta_min = int((event.scheduled_ts - asof).total_seconds() / 60)
        overrides = EVENT_TYPE_OVERRIDES.get(event.event_type, {})
        post_digest = int(overrides.get("post_digest_minutes", self.config.EVENT_POST_DIGESTION_MINUTES))
        headline = int(overrides.get("headline_risk_minutes", 0))

        if 0 <= delta_min <= self.config.EVENT_PRE_LOCKOUT_MINUTES:
            return "pre_event_lockout"
        if -2 <= delta_min < 0:
            return "release_window"
        if -post_digest <= delta_min < -2:
            return "post_event_digestion"
        if -self.config.EVENT_SPREAD_NORMALIZATION_WINDOW_MINUTES <= delta_min < -2:
            return "spread_normalization_pending"
        if headline and -headline <= delta_min < 0:
            return "headline_risk"
        return "normal"

    def build_event_decision(self, asof: datetime, instruments: list[str], market_intel_snapshots: dict[str, dict]) -> EventDecision:
        asof = asof if asof.tzinfo else asof.replace(tzinfo=timezone.utc)
        events = self._load_events()

        if not events and self.config.EVENT_BLOCK_NEW_POSITIONS_IF_CALENDAR_UNAVAILABLE:
            return EventDecision(
                asof=asof,
                event_state="calendar_degraded",
                event_phase="headline_risk",
                active_events=[],
                minutes_to_next_high_impact=None,
                minutes_since_last_high_impact=None,
                pre_event_lockout=True,
                post_event_digestion=False,
                spread_normalized=False,
                allow_breakout=False,
                allow_mean_reversion=False,
                allow_sweep_reversal=False,
                allow_trend_pullback=False,
                event_risk_multiplier=0.6,
                execution_penalty_multiplier=1.8,
                reason_codes=[EVENT_CALENDAR_UNAVAILABLE],
            )

        relevant: list[NormalizedEvent] = []
        for ins in sorted(set(instruments)):
            relevant.extend(self.get_relevant_events(ins, asof, events))
        relevant = sorted({e.event_id: e for e in relevant}.values(), key=lambda e: e.scheduled_ts)

        phase = "normal"
        for event in relevant:
            candidate_phase = self.classify_event_phase(asof, event)
            if candidate_phase != "normal":
                phase = candidate_phase
                break

        policy = EVENT_PHASE_POLICIES[phase]
        reason_codes = [EVENT_NORMAL]
        if phase == "pre_event_lockout":
            reason_codes = [EVENT_PRE_LOCKOUT, EVENT_REVERSION_BLOCKED]
        elif phase == "release_window":
            reason_codes = [EVENT_HIGH_IMPACT_ACTIVE, EVENT_SPREAD_NOT_NORMALIZED]
        elif phase in {"post_event_digestion", "spread_normalization_pending"}:
            reason_codes = [EVENT_POST_DIGESTION, EVENT_RECENT_HIGH_IMPACT]
        elif phase == "headline_risk":
            reason_codes = [EVENT_POWELL_HEADLINE_RISK]

        highs = [e for e in events if e.impact in {"high", "3"}]
        mins_to = None
        mins_since = None
        if highs:
            deltas = [int((e.scheduled_ts - asof).total_seconds() / 60) for e in highs]
            future = [d for d in deltas if d >= 0]
            past = [-d for d in deltas if d < 0]
            mins_to = min(future) if future else None
            mins_since = min(past) if past else None

        active_events = [
            {
                "event_id": e.event_id,
                "title": e.title,
                "currency": e.currency,
                "impact": e.impact,
                "event_type": e.event_type,
                "minutes_to": int((e.scheduled_ts - asof).total_seconds() / 60),
            }
            for e in relevant[:6]
        ]

        state = "normal" if phase == "normal" else {
            "pre_event_lockout": "high_impact_pending",
            "release_window": "release_active",
            "post_event_digestion": "post_release_digestion",
            "spread_normalization_pending": "spread_normalization_pending",
            "headline_risk": "headline_risk",
        }[phase]

        return EventDecision(
            asof=asof,
            event_state=state,
            event_phase=phase,
            active_events=active_events,
            minutes_to_next_high_impact=mins_to,
            minutes_since_last_high_impact=mins_since,
            pre_event_lockout=phase == "pre_event_lockout",
            post_event_digestion=phase in {"post_event_digestion", "spread_normalization_pending"},
            spread_normalized=phase in {"normal", "post_event_tradable"},
            allow_breakout=policy["allow_breakout"],
            allow_mean_reversion=policy["allow_mean_reversion"],
            allow_sweep_reversal=policy["allow_sweep_reversal"],
            allow_trend_pullback=policy["allow_trend_pullback"],
            event_risk_multiplier=policy["risk"],
            execution_penalty_multiplier=policy["exec_pen"],
            reason_codes=reason_codes,
        )
