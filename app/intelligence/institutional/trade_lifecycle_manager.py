from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.intelligence.institutional.schemas import (
    LifecycleSnapshot,
    LifecycleTransition,
    PositionState,
    ReasonCode,
)


@dataclass(frozen=True)
class PositionAdjustment:
    move_stop_to: float | None = None
    reduce_by: float = 0.0
    scale_in_by: float = 0.0
    hedge_ratio: float = 0.0
    force_exit: bool = False
    reason: str = ""


class TimeStopController:
    def evaluate(self, snapshot: LifecycleSnapshot, *, expected_holding_bars: int) -> bool:
        if snapshot.bars_open <= expected_holding_bars:
            return False
        return snapshot.unrealized_r < 0.20


class ThesisInvalidationMonitor:
    def evaluate(self, snapshot: LifecycleSnapshot) -> bool:
        if snapshot.thesis_score < 0.25:
            return True
        if snapshot.unrealized_r < -1.1 and snapshot.thesis_score < 0.40:
            return True
        return False


class DynamicExitEngine:
    def evaluate(self, snapshot: LifecycleSnapshot) -> PositionAdjustment:
        if snapshot.state in {PositionState.CLOSED, PositionState.POSTMORTEM_PENDING}:
            return PositionAdjustment()

        if snapshot.event_risk_score > 0.9:
            return PositionAdjustment(force_exit=True, reason=ReasonCode.LIFECYCLE_EVENT_EXIT.value)

        if snapshot.max_favorable_excursion_r > 1.2 and snapshot.unrealized_r < snapshot.max_favorable_excursion_r * 0.45:
            return PositionAdjustment(reduce_by=0.35, reason="protect_profit_after_pullback")

        if snapshot.unrealized_r > 0.9:
            tightened_stop = snapshot.current_price - (snapshot.current_price - snapshot.avg_entry_price) * 0.35
            return PositionAdjustment(move_stop_to=max(snapshot.stop_price, tightened_stop), reason="activate_volatility_trailing")

        if snapshot.unrealized_r < -0.9:
            return PositionAdjustment(reduce_by=0.50, reason="loss_containment_reduce")

        return PositionAdjustment()


class PositionAdjustmentPolicy:
    def evaluate(self, snapshot: LifecycleSnapshot) -> PositionAdjustment:
        if snapshot.state == PositionState.ACTIVE and snapshot.unrealized_r > 0.5 and snapshot.thesis_score > 0.65:
            return PositionAdjustment(scale_in_by=0.20, reason="scale_in_with_strength")
        if snapshot.state == PositionState.TIME_DECAY_WATCH and snapshot.unrealized_r < 0.10:
            return PositionAdjustment(reduce_by=0.25, reason="time_decay_reduce")
        if snapshot.state == PositionState.EMERGENCY_EXIT_CANDIDATE:
            return PositionAdjustment(force_exit=True, reason="emergency_exit_policy")
        return PositionAdjustment()


class PositionStateMachine:
    def next_state(self, snapshot: LifecycleSnapshot, *, force_exit: bool, time_stop: bool, thesis_invalidated: bool, has_trailing: bool) -> PositionState:
        if force_exit:
            return PositionState.EMERGENCY_EXIT_CANDIDATE
        if thesis_invalidated:
            return PositionState.EMERGENCY_EXIT_CANDIDATE
        if time_stop:
            return PositionState.TIME_DECAY_WATCH
        if snapshot.fill_ratio < 1.0 and snapshot.state in {PositionState.PROPOSED, PositionState.STAGED, PositionState.PARTIALLY_FILLED}:
            return PositionState.PARTIALLY_FILLED
        if has_trailing and snapshot.unrealized_r > 0.8:
            return PositionState.TRAILING
        if snapshot.state in {PositionState.PROPOSED, PositionState.STAGED, PositionState.PARTIALLY_FILLED, PositionState.TIME_DECAY_WATCH}:
            return PositionState.ACTIVE
        return snapshot.state


class TradeLifecycleManager:
    def __init__(self) -> None:
        self._snapshots: dict[str, LifecycleSnapshot] = {}
        self._history: list[LifecycleTransition] = []

        self.time_stop = TimeStopController()
        self.thesis_monitor = ThesisInvalidationMonitor()
        self.exit_engine = DynamicExitEngine()
        self.adjust_policy = PositionAdjustmentPolicy()
        self.machine = PositionStateMachine()

    def stage(
        self,
        *,
        trade_id: str,
        confidence: float,
        entry_price: float,
        stop_price: float,
        target_price: float,
    ) -> LifecycleSnapshot:
        snap = LifecycleSnapshot(
            trade_id=trade_id,
            state=PositionState.STAGED,
            confidence=confidence,
            bars_open=0,
            fill_ratio=0.0,
            avg_entry_price=entry_price,
            current_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            realized_r=0.0,
            unrealized_r=0.0,
            max_favorable_excursion_r=0.0,
            max_adverse_excursion_r=0.0,
            thesis_score=confidence,
            event_risk_score=0.0,
            notes=[],
        )
        self._snapshots[trade_id] = snap
        return snap

    def update(
        self,
        *,
        trade_id: str,
        timestamp: datetime,
        fill_ratio: float,
        current_price: float,
        bars_open: int,
        thesis_score: float,
        event_risk_score: float,
        expected_holding_bars: int,
    ) -> LifecycleSnapshot:
        snap = self._snapshots[trade_id]
        risk = abs(snap.avg_entry_price - snap.stop_price)
        if risk <= 1e-9:
            unrealized_r = 0.0
        else:
            unrealized_r = (current_price - snap.avg_entry_price) / risk

        mfe = max(snap.max_favorable_excursion_r, unrealized_r)
        mae = min(snap.max_adverse_excursion_r, unrealized_r)

        next_snapshot = LifecycleSnapshot(
            trade_id=snap.trade_id,
            state=snap.state,
            confidence=snap.confidence,
            bars_open=bars_open,
            fill_ratio=fill_ratio,
            avg_entry_price=snap.avg_entry_price,
            current_price=current_price,
            stop_price=snap.stop_price,
            target_price=snap.target_price,
            realized_r=snap.realized_r,
            unrealized_r=unrealized_r,
            max_favorable_excursion_r=mfe,
            max_adverse_excursion_r=mae,
            thesis_score=thesis_score,
            event_risk_score=event_risk_score,
            notes=[*snap.notes],
        )

        dyn_adjust = self.exit_engine.evaluate(next_snapshot)
        policy_adjust = self.adjust_policy.evaluate(next_snapshot)

        force_exit = dyn_adjust.force_exit or policy_adjust.force_exit
        tstop = self.time_stop.evaluate(next_snapshot, expected_holding_bars=expected_holding_bars)
        thesis_invalidated = self.thesis_monitor.evaluate(next_snapshot)
        has_trailing = dyn_adjust.move_stop_to is not None

        new_state = self.machine.next_state(
            next_snapshot,
            force_exit=force_exit,
            time_stop=tstop,
            thesis_invalidated=thesis_invalidated,
            has_trailing=has_trailing,
        )

        new_stop = next_snapshot.stop_price
        if dyn_adjust.move_stop_to is not None:
            new_stop = max(new_stop, dyn_adjust.move_stop_to)

        notes = [*next_snapshot.notes]
        for adj in (dyn_adjust, policy_adjust):
            if adj.reason:
                notes.append(adj.reason)
        if tstop:
            notes.append(ReasonCode.LIFECYCLE_TIME_DECAY.value)
        if thesis_invalidated:
            notes.append(ReasonCode.LIFECYCLE_THESIS_INVALIDATED.value)

        mutated = LifecycleSnapshot(
            trade_id=next_snapshot.trade_id,
            state=new_state,
            confidence=next_snapshot.confidence,
            bars_open=next_snapshot.bars_open,
            fill_ratio=next_snapshot.fill_ratio,
            avg_entry_price=next_snapshot.avg_entry_price,
            current_price=next_snapshot.current_price,
            stop_price=new_stop,
            target_price=next_snapshot.target_price,
            realized_r=next_snapshot.realized_r,
            unrealized_r=next_snapshot.unrealized_r,
            max_favorable_excursion_r=next_snapshot.max_favorable_excursion_r,
            max_adverse_excursion_r=next_snapshot.max_adverse_excursion_r,
            thesis_score=next_snapshot.thesis_score,
            event_risk_score=next_snapshot.event_risk_score,
            notes=notes,
        )

        if mutated.state != snap.state:
            self._history.append(
                LifecycleTransition(
                    trade_id=trade_id,
                    from_state=snap.state,
                    to_state=mutated.state,
                    reason=notes[-1] if notes else "state_transition",
                    timestamp=timestamp,
                )
            )

        self._snapshots[trade_id] = mutated
        return mutated

    def close(self, *, trade_id: str, timestamp: datetime, final_realized_r: float, reason: str) -> LifecycleSnapshot:
        snap = self._snapshots[trade_id]
        final = LifecycleSnapshot(
            trade_id=snap.trade_id,
            state=PositionState.CLOSED,
            confidence=snap.confidence,
            bars_open=snap.bars_open,
            fill_ratio=1.0,
            avg_entry_price=snap.avg_entry_price,
            current_price=snap.current_price,
            stop_price=snap.stop_price,
            target_price=snap.target_price,
            realized_r=final_realized_r,
            unrealized_r=0.0,
            max_favorable_excursion_r=snap.max_favorable_excursion_r,
            max_adverse_excursion_r=snap.max_adverse_excursion_r,
            thesis_score=snap.thesis_score,
            event_risk_score=snap.event_risk_score,
            notes=[*snap.notes, reason],
        )
        self._history.append(
            LifecycleTransition(
                trade_id=trade_id,
                from_state=snap.state,
                to_state=PositionState.CLOSED,
                reason=reason,
                timestamp=timestamp,
            )
        )
        self._snapshots[trade_id] = final
        return final

    def postmortem_pending(self, *, trade_id: str, timestamp: datetime) -> LifecycleSnapshot:
        snap = self._snapshots[trade_id]
        pm = LifecycleSnapshot(
            trade_id=snap.trade_id,
            state=PositionState.POSTMORTEM_PENDING,
            confidence=snap.confidence,
            bars_open=snap.bars_open,
            fill_ratio=snap.fill_ratio,
            avg_entry_price=snap.avg_entry_price,
            current_price=snap.current_price,
            stop_price=snap.stop_price,
            target_price=snap.target_price,
            realized_r=snap.realized_r,
            unrealized_r=snap.unrealized_r,
            max_favorable_excursion_r=snap.max_favorable_excursion_r,
            max_adverse_excursion_r=snap.max_adverse_excursion_r,
            thesis_score=snap.thesis_score,
            event_risk_score=snap.event_risk_score,
            notes=[*snap.notes, "postmortem_pending"],
        )
        self._history.append(
            LifecycleTransition(
                trade_id=trade_id,
                from_state=snap.state,
                to_state=PositionState.POSTMORTEM_PENDING,
                reason="postmortem_pending",
                timestamp=timestamp,
            )
        )
        self._snapshots[trade_id] = pm
        return pm

    @property
    def transitions(self) -> list[LifecycleTransition]:
        return list(self._history)

    @property
    def snapshots(self) -> dict[str, LifecycleSnapshot]:
        return dict(self._snapshots)


__all__ = [
    "DynamicExitEngine",
    "PositionAdjustment",
    "PositionAdjustmentPolicy",
    "PositionStateMachine",
    "ThesisInvalidationMonitor",
    "TimeStopController",
    "TradeLifecycleManager",
]
