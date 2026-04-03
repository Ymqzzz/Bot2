from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from app.intelligence.institutional.schemas import EventWindow, SessionDecision, SessionProfile


@dataclass(frozen=True)
class MarketClockState:
    active_session: str
    transition_risk: float
    near_rollover: bool
    near_weekend: bool


class MarketClock:
    def now_state(self, now: datetime) -> MarketClockState:
        t = now.time()
        weekday = now.weekday()

        if time(21, 0) <= t or t < time(1, 0):
            session = "asia_open"
        elif time(1, 0) <= t < time(7, 0):
            session = "asia_mid"
        elif time(7, 0) <= t < time(10, 0):
            session = "london_open"
        elif time(10, 0) <= t < time(12, 0):
            session = "london_mid"
        elif time(12, 0) <= t < time(14, 0):
            session = "ny_lunch"
        elif time(14, 0) <= t < time(16, 0):
            session = "ny_close"
        else:
            session = "transition"

        transition_risk = 0.0
        if session in {"asia_open", "london_open", "ny_close", "transition"}:
            transition_risk = 0.65
        elif session in {"ny_lunch"}:
            transition_risk = 0.55
        else:
            transition_risk = 0.35

        near_rollover = time(21, 45) <= t <= time(22, 15)
        near_weekend = weekday == 4 and t >= time(17, 0)
        return MarketClockState(session, transition_risk, near_rollover, near_weekend)


class SessionBehaviorProfiles:
    def __init__(self) -> None:
        self.profiles: dict[str, SessionProfile] = {
            "asia_open": SessionProfile("asia_open", 1.05, 0.9, 0.55, 0.45),
            "asia_mid": SessionProfile("asia_mid", 1.1, 0.75, 0.45, 0.30),
            "london_open": SessionProfile("london_open", 1.0, 1.0, 0.85, 0.60),
            "london_mid": SessionProfile("london_mid", 1.05, 0.95, 0.70, 0.45),
            "ny_lunch": SessionProfile("ny_lunch", 1.2, 0.6, 0.35, 0.35),
            "ny_close": SessionProfile("ny_close", 1.1, 0.75, 0.50, 0.70),
            "transition": SessionProfile("transition", 1.25, 0.65, 0.30, 0.65),
        }

    def profile(self, name: str) -> SessionProfile:
        return self.profiles.get(name, self.profiles["transition"])


class EventRiskCalendarAdapter:
    def __init__(self) -> None:
        self._windows: list[EventWindow] = []

    def set_windows(self, windows: list[EventWindow]) -> None:
        self._windows = sorted(windows, key=lambda x: x.start)

    def active_windows(self, now: datetime) -> list[EventWindow]:
        return [w for w in self._windows if w.start <= now <= w.end]

    def minutes_to_next(self, now: datetime) -> int | None:
        future = [w for w in self._windows if w.start > now]
        if not future:
            return None
        delta = future[0].start - now
        return max(0, int(delta.total_seconds() // 60))


class TimeOfDayEdgeModel:
    def edge_multiplier(self, profile: SessionProfile, event_severity: float, event_relevance: float, transition_risk: float) -> float:
        event_penalty = event_severity * event_relevance * 0.45
        transition_penalty = transition_risk * 0.20
        return max(0.7, min(1.5, profile.edge_threshold_multiplier + event_penalty + transition_penalty))

    def size_multiplier(self, profile: SessionProfile, event_severity: float, transition_risk: float, liquidity_score: float) -> float:
        event_drag = event_severity * 0.45
        transition_drag = transition_risk * 0.25
        liquidity_boost = max(0.0, liquidity_score - 0.5) * 0.25
        return max(0.25, min(1.15, profile.size_multiplier - event_drag - transition_drag + liquidity_boost))


class SessionIntelligenceEngine:
    def __init__(self) -> None:
        self.clock = MarketClock()
        self.profiles = SessionBehaviorProfiles()
        self.calendar = EventRiskCalendarAdapter()
        self.edge = TimeOfDayEdgeModel()

    def assess(self, *, now: datetime, external_event_windows: list[EventWindow] | None = None) -> SessionDecision:
        if external_event_windows is not None:
            self.calendar.set_windows(external_event_windows)

        clock_state = self.clock.now_state(now)
        profile = self.profiles.profile(clock_state.active_session)

        active = self.calendar.active_windows(now)
        severity = max((w.severity for w in active), default=0.0)
        relevance = max((w.relevance for w in active), default=0.0)

        mins_to_next = self.calendar.minutes_to_next(now)
        pre_event_risk = 0.0
        if mins_to_next is not None:
            if mins_to_next <= 15:
                pre_event_risk = 0.9
            elif mins_to_next <= 45:
                pre_event_risk = 0.55
            elif mins_to_next <= 90:
                pre_event_risk = 0.25

        effective_event_severity = max(severity, pre_event_risk)
        edge_mult = self.edge.edge_multiplier(profile, effective_event_severity, max(0.1, relevance), clock_state.transition_risk)
        size_mult = self.edge.size_multiplier(profile, effective_event_severity, clock_state.transition_risk, profile.liquidity_score)

        liquidity_penalty = max(0.0, 0.75 - profile.liquidity_score)
        block_new_risk = (
            effective_event_severity * max(0.2, relevance) > 0.62
            or clock_state.near_rollover
            or clock_state.near_weekend
        )

        return SessionDecision(
            active_session=clock_state.active_session,
            edge_multiplier=edge_mult,
            size_multiplier=size_mult,
            block_new_risk=block_new_risk,
            transition_risk=clock_state.transition_risk,
            liquidity_penalty=liquidity_penalty,
        )


__all__ = [
    "EventRiskCalendarAdapter",
    "MarketClock",
    "MarketClockState",
    "SessionBehaviorProfiles",
    "SessionIntelligenceEngine",
    "TimeOfDayEdgeModel",
]
