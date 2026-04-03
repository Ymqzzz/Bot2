from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass
class RuntimeSnapshot:
    """Shared runtime state passed across the full orchestration lifecycle."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    equity: float = 0.0
    pnl: float = 0.0
    open_risk: float = 0.0
    session: str = "unknown"
    regime: str = "unknown"
    health_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class RuntimeCycleInput:
    instruments: list[str]
    market_data: dict[str, Any]
    bars: dict[str, Any]
    open_positions: list[dict[str, Any]]
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeCycleResult:
    snapshot: RuntimeSnapshot
    candidates: list[dict[str, Any]]
    approved_candidates: list[dict[str, Any]]
    execution_plan: dict[str, Any]
    persisted_records: dict[str, Any]


class TradeIntelAdapter(Protocol):
    def generate_candidates(self, cycle_input: RuntimeCycleInput, snapshot: RuntimeSnapshot) -> list[dict[str, Any]]:
        ...


class ControlPlaneAdapter(Protocol):
    def evaluate(
        self,
        cycle_input: RuntimeCycleInput,
        snapshot: RuntimeSnapshot,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ...


class ResearchCoreAdapter(Protocol):
    def review(
        self,
        cycle_input: RuntimeCycleInput,
        snapshot: RuntimeSnapshot,
        candidates: list[dict[str, Any]],
        control_plane_state: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class EventAuditStoreAdapter(Protocol):
    def persist_cycle(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class RuntimeCoordinator:
    """Canonical runtime orchestration engine.

    cycle = data ingest -> candidate generation -> policy/risk/governance
            -> execution plan -> event/audit persistence
    """

    def __init__(
        self,
        control_plane: ControlPlaneAdapter,
        trade_intel: TradeIntelAdapter,
        research_core: ResearchCoreAdapter,
        store: EventAuditStoreAdapter,
    ) -> None:
        self.control_plane = control_plane
        self.trade_intel = trade_intel
        self.research_core = research_core
        self.store = store

    def run_cycle(self, cycle_input: RuntimeCycleInput, snapshot: RuntimeSnapshot) -> RuntimeCycleResult:
        snapshot.timestamp = datetime.now(timezone.utc)
        candidates = self.trade_intel.generate_candidates(cycle_input, snapshot)
        control_plane_state, governance_state = self._evaluate_gates(cycle_input, snapshot, candidates)
        approved_candidates = self._build_approved_candidates(candidates, control_plane_state, governance_state)
        execution_plan = self._build_execution_plan(snapshot, approved_candidates, control_plane_state, governance_state)
        persisted = self.store.persist_cycle(
            self._build_persistence_payload(snapshot, candidates, control_plane_state, governance_state, execution_plan)
        )

        return RuntimeCycleResult(
            snapshot=snapshot,
            candidates=candidates,
            approved_candidates=approved_candidates,
            execution_plan=execution_plan,
            persisted_records=persisted,
        )

    def _evaluate_gates(
        self,
        cycle_input: RuntimeCycleInput,
        snapshot: RuntimeSnapshot,
        candidates: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        control_plane_state = self.control_plane.evaluate(cycle_input, snapshot, candidates)
        governance_state = self.research_core.review(cycle_input, snapshot, candidates, control_plane_state)
        return control_plane_state, governance_state

    def _build_approved_candidates(
        self,
        candidates: list[dict[str, Any]],
        control_plane_state: dict[str, Any],
        governance_state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        approved_ids = set(control_plane_state.get("approved_candidate_ids", []))
        rejected_by_research = set(governance_state.get("rejected_candidate_ids", []))

        return [
            candidate
            for candidate in candidates
            if self._candidate_id(candidate) in approved_ids and self._candidate_id(candidate) not in rejected_by_research
        ]

    def _build_execution_plan(
        self,
        snapshot: RuntimeSnapshot,
        approved_candidates: list[dict[str, Any]],
        control_plane_state: dict[str, Any],
        governance_state: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "asof": snapshot.timestamp.isoformat(),
            "approved_candidate_ids": [self._candidate_id(candidate) for candidate in approved_candidates],
            "tactics": control_plane_state.get("tactics", {}),
            "governance": governance_state,
        }

    def _build_persistence_payload(
        self,
        snapshot: RuntimeSnapshot,
        candidates: list[dict[str, Any]],
        control_plane_state: dict[str, Any],
        governance_state: dict[str, Any],
        execution_plan: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "snapshot": {
                "timestamp": snapshot.timestamp.isoformat(),
                "equity": snapshot.equity,
                "pnl": snapshot.pnl,
                "open_risk": snapshot.open_risk,
                "session": snapshot.session,
                "regime": snapshot.regime,
                "health_scores": snapshot.health_scores,
            },
            "candidates": candidates,
            "control_plane": control_plane_state,
            "research_core": governance_state,
            "execution_plan": execution_plan,
        }

    @staticmethod
    def _candidate_id(candidate: dict[str, Any]) -> str | None:
        return candidate.get("candidate_id")


class JsonlEventAuditStore:
    def __init__(self, append_fn):
        self.append_fn = append_fn

    def persist_cycle(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.append_fn(payload)
        return {"persisted": True, "record_type": "runtime_cycle"}
