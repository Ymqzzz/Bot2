from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import ControlPlaneConfig
from .event_calendar import NormalizedEvent, normalize_events
from .event_policies import EVENT_PHASE_POLICIES, EVENT_TYPE_OVERRIDES

from .config import ControlPlaneConfig
from .event_calendar import normalize_calendar
from .event_policies import EVENT_PHASE_POLICIES
from .models import EventDecision
from .reason_codes import *


class EventEngine:
    def __init__(self, config: ControlPlaneConfig):
        self.config = config
        self._events: list[NormalizedEvent] = []

    def set_calendar_events(self, raw_events: list[dict[str, Any]]) -> None:
        self._events = normalize_events(raw_events)

    def get_relevant_events(self, instrument: str, asof: datetime) -> list[NormalizedEvent]:
        base, quote = instrument.split("_") if "_" in instrument else (instrument[:3], instrument[3:])
        return [e for e in self._events if e.currency in {base, quote, "USD"} and abs((e.scheduled_ts - asof).total_seconds()) <= 6 * 3600]

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
        if not self._events and self.config.EVENT_BLOCK_NEW_POSITIONS_IF_CALENDAR_UNAVAILABLE:
            return EventDecision(
                asof=asof, event_state="calendar_degraded", event_phase="headline_risk", active_events=[],
                minutes_to_next_high_impact=None, minutes_since_last_high_impact=None, pre_event_lockout=True,
                post_event_digestion=False, spread_normalized=False, allow_breakout=False, allow_mean_reversion=False,
                allow_sweep_reversal=False, allow_trend_pullback=False, event_risk_multiplier=0.6,
                execution_penalty_multiplier=1.8, reason_codes=[EVENT_CALENDAR_UNAVAILABLE]
            )

        relevant: list[NormalizedEvent] = []
        for ins in sorted(set(instruments)):
            relevant.extend(self.get_relevant_events(ins, asof))
        relevant = sorted({e.event_id: e for e in relevant}.values(), key=lambda e: e.scheduled_ts)

        phase = "normal"
        reason_codes = [EVENT_NORMAL]
        for e in relevant:
            p = self.classify_event_phase(asof, e)
            if p != "normal":
                phase = p
                break

        policy = EVENT_PHASE_POLICIES[phase]
        if phase == "pre_event_lockout":
            reason_codes = [EVENT_PRE_LOCKOUT, EVENT_REVERSION_BLOCKED]
        elif phase == "release_window":
            reason_codes = [EVENT_HIGH_IMPACT_ACTIVE, EVENT_SPREAD_NOT_NORMALIZED]
        elif phase in {"post_event_digestion", "spread_normalization_pending"}:
            reason_codes = [EVENT_POST_DIGESTION, EVENT_RECENT_HIGH_IMPACT]
        elif phase == "headline_risk":
            reason_codes = [EVENT_POWELL_HEADLINE_RISK]

        high = [e for e in self._events if e.impact in {"high", "3"}]
        mins_to = None
        mins_since = None
        if high:
            deltas = [int((e.scheduled_ts - asof).total_seconds() / 60) for e in high]
            future = [d for d in deltas if d >= 0]
            past = [-d for d in deltas if d < 0]
            mins_to = min(future) if future else None
            mins_since = min(past) if past else None

        active_events = [
            {"event_id": e.event_id, "title": e.title, "currency": e.currency, "impact": e.impact, "event_type": e.event_type,
             "minutes_to": int((e.scheduled_ts - asof).total_seconds() / 60)}
            for e in relevant[:6]
        ]
        state = "normal" if phase == "normal" else {
            "pre_event_lockout": "high_impact_pending", "release_window": "release_active", "post_event_digestion": "post_release_digestion",
            "spread_normalization_pending": "spread_normalization_pending", "headline_risk": "headline_risk"
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
    def __init__(self, config: ControlPlaneConfig | None = None, calendar_provider=None) -> None:
        self.config = config or ControlPlaneConfig()
        self.calendar_provider = calendar_provider or (lambda: [])

    def get_relevant_events(self, instrument: str, asof: datetime) -> list:
        ccy = instrument.split("_")
        events = normalize_calendar(self.calendar_provider() or [])
        return [e for e in events if e["currency"] in ccy and abs((e["scheduled_ts"] - asof).total_seconds()) < 6 * 3600]

    def classify_event_phase(self, asof: datetime, event: dict) -> str:
        delta = (event["scheduled_ts"] - asof).total_seconds() / 60
        if -2 <= delta <= 3:
            return "release_window"
        if 0 < delta <= self.config.EVENT_PRE_LOCKOUT_MINUTES:
            return "pre_event_lockout"
        if -self.config.EVENT_SPREAD_NORMALIZATION_WINDOW_MINUTES <= delta < -self.config.EVENT_POST_DIGESTION_MINUTES:
            return "spread_normalization_pending"
        if -self.config.EVENT_POST_DIGESTION_MINUTES <= delta < -3:
            return "post_event_digestion"
        if delta < -self.config.EVENT_POST_DIGESTION_MINUTES:
            return "post_event_tradable"
        return "normal"

    def build_event_decision(self, asof: datetime, instruments, market_intel_snapshots) -> EventDecision:
        asof = asof if asof.tzinfo else asof.replace(tzinfo=timezone.utc)
        try:
            raw = self.calendar_provider() if self.config.EVENT_CALENDAR_ENABLED else []
        except Exception:
            raw = []
        if not raw:
            return EventDecision(
                asof=asof, event_state="calendar_degraded", event_phase="normal", active_events=[],
                minutes_to_next_high_impact=None, minutes_since_last_high_impact=None,
                pre_event_lockout=False, post_event_digestion=False, spread_normalized=True,
                allow_breakout=not self.config.EVENT_BLOCK_NEW_POSITIONS_IF_CALENDAR_UNAVAILABLE,
                allow_mean_reversion=not self.config.EVENT_BLOCK_NEW_POSITIONS_IF_CALENDAR_UNAVAILABLE,
                allow_sweep_reversal=not self.config.EVENT_BLOCK_NEW_POSITIONS_IF_CALENDAR_UNAVAILABLE,
                allow_trend_pullback=True, event_risk_multiplier=0.8, execution_penalty_multiplier=1.2,
                reason_codes=[EVENT_CALENDAR_UNAVAILABLE],
            )
        events = normalize_calendar(raw)
        highs = [e for e in events if e["impact"] in {"high", "3"}]
        nxt = next((e for e in highs if e["scheduled_ts"] >= asof), None)
        prev = next((e for e in reversed(highs) if e["scheduled_ts"] <= asof), None)
        phase = "normal"
        active = []
        for e in events:
            p = self.classify_event_phase(asof, e)
            if p != "normal":
                active.append({"event_id": e["event_id"], "currency": e["currency"], "impact": e["impact"], "phase": p, "title": e["title"]})
                if p in {"release_window", "headline_risk", "pre_event_lockout", "spread_normalization_pending", "post_event_digestion"}:
                    phase = p
                    break
        pol = EVENT_PHASE_POLICIES[phase]
        reasons = [EVENT_NORMAL]
        if phase == "pre_event_lockout": reasons = [EVENT_PRE_LOCKOUT, EVENT_REVERSION_BLOCKED]
        if phase == "release_window": reasons = [EVENT_HIGH_IMPACT_ACTIVE, EVENT_REVERSION_BLOCKED]
        if phase == "post_event_digestion": reasons = [EVENT_POST_DIGESTION]
        if phase == "spread_normalization_pending": reasons = [EVENT_SPREAD_NOT_NORMALIZED]
        if any("POWELL" in a.get("title", "").upper() for a in active):
            phase = "headline_risk"
            pol = EVENT_PHASE_POLICIES[phase]
            reasons.append(EVENT_POWELL_HEADLINE_RISK)
        state_map = {
            "normal": "normal", "pre_event_lockout": "high_impact_pending", "release_window": "release_active",
            "post_event_digestion": "post_release_digestion", "spread_normalization_pending": "spread_normalization_pending",
            "post_event_tradable": "elevated_risk", "headline_risk": "headline_risk"
        }
        return EventDecision(
            asof=asof,
            event_state=state_map.get(phase, "normal"),
            event_phase=phase,
            active_events=active,
            minutes_to_next_high_impact=int((nxt["scheduled_ts"] - asof).total_seconds() / 60) if nxt else None,
            minutes_since_last_high_impact=int((asof - prev["scheduled_ts"]).total_seconds() / 60) if prev else None,
            pre_event_lockout=phase == "pre_event_lockout",
            post_event_digestion=phase in {"post_event_digestion", "post_event_tradable"},
            spread_normalized=phase not in {"release_window", "spread_normalization_pending"},
            allow_breakout=pol["allow_breakout"],
            allow_mean_reversion=pol["allow_mean_reversion"],
            allow_sweep_reversal=pol["allow_sweep_reversal"],
            allow_trend_pullback=pol["allow_trend_pullback"],
            event_risk_multiplier=pol["risk"],
            execution_penalty_multiplier=pol["exec_penalty"],
            reason_codes=reasons,
        )
