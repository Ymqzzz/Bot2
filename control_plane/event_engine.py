from __future__ import annotations

from datetime import datetime, timezone

from .config import ControlPlaneConfig
from .event_calendar import normalize_calendar
from .event_policies import EVENT_PHASE_POLICIES
from .models import EventDecision
from .reason_codes import *


class EventEngine:
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
