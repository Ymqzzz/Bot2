from app.runtime.engine import RuntimeCoordinator, RuntimeCycleInput, RuntimeSnapshot


class _TradeIntel:
    def generate_candidates(self, _cycle_input, _snapshot):
        return [
            {"candidate_id": "A", "instrument": "EUR_USD"},
            {"candidate_id": "B", "instrument": "GBP_USD"},
            {"instrument": "USD_JPY"},
        ]


class _ControlPlane:
    def evaluate(self, _cycle_input, _snapshot, _candidates):
        return {"approved_candidate_ids": ["A", "B"], "tactics": {"A": "passive"}}


class _ResearchCore:
    def review(self, _cycle_input, _snapshot, _candidates, _control_plane_state):
        return {"rejected_candidate_ids": ["B"], "notes": ["risk_event"]}


class _Store:
    def __init__(self):
        self.payloads = []

    def persist_cycle(self, payload):
        self.payloads.append(payload)
        return {"persisted": True, "records": len(self.payloads)}


def test_runtime_coordinator_filters_approved_candidates_and_persists_payload():
    store = _Store()
    coordinator = RuntimeCoordinator(
        control_plane=_ControlPlane(),
        trade_intel=_TradeIntel(),
        research_core=_ResearchCore(),
        store=store,
    )
    cycle_input = RuntimeCycleInput(
        instruments=["EUR_USD", "GBP_USD"],
        market_data={},
        bars={},
        open_positions=[],
    )
    snapshot = RuntimeSnapshot(equity=100_000.0, pnl=500.0, open_risk=1_000.0, session="london", regime="trend")

    result = coordinator.run_cycle(cycle_input, snapshot)

    assert [c["candidate_id"] for c in result.approved_candidates] == ["A"]
    assert result.execution_plan["approved_candidate_ids"] == ["A"]
    assert result.execution_plan["tactics"] == {"A": "passive"}
    assert result.persisted_records == {"persisted": True, "records": 1}
    assert store.payloads[0]["snapshot"]["equity"] == 100_000.0
    assert store.payloads[0]["research_core"]["rejected_candidate_ids"] == ["B"]
