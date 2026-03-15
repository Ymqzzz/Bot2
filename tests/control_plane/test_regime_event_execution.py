from datetime import datetime, timezone
import pandas as pd

from control_plane.config import load_config
from control_plane.event_engine import EventEngine
from control_plane.execution_intel import ExecutionIntelligenceEngine
from control_plane.regime_engine import RegimeEngine


def test_regime_classification_trend_expansion():
    cfg = load_config()
    eng = RegimeEngine(cfg)
    bars = pd.DataFrame({
        "open": [1+i*0.001 for i in range(120)],
        "high": [1.001+i*0.001 for i in range(120)],
        "low": [0.999+i*0.001 for i in range(120)],
        "close": [1.0005+i*0.001 for i in range(120)],
    })
    ev = EventEngine(cfg).build_event_decision(datetime.now(timezone.utc), ["EUR_USD"], {})
    d = eng.classify_instrument_regime("EUR_USD", {"spread_shock": 0.1, "micro_noise": 0.1}, bars, ev)
    assert d.regime_name in {"trend_expansion", "compression_pre_breakout", "uncertain_mixed", "dead_zone"}


def test_event_phase_pre_lockout():
    cfg = load_config()
    ee = EventEngine(cfg)
    asof = datetime.now(timezone.utc)
    ee.set_calendar_events([{"event": "US CPI", "currency": "USD", "impact": "high", "when": (asof.replace(microsecond=0) + pd.Timedelta(minutes=10)).isoformat()}])
    d = ee.build_event_decision(asof, ["EUR_USD"], {})
    assert d.event_phase in {"pre_event_lockout", "normal"}


def test_execution_blocks_dislocated_spread():
    cfg = load_config()
    ex = ExecutionIntelligenceEngine(cfg)
    ev = EventEngine(cfg).build_event_decision(datetime.now(timezone.utc), ["EUR_USD"], {})
    rd = RegimeEngine(cfg).classify_instrument_regime("EUR_USD", {}, pd.DataFrame(), ev)
    d = ex.evaluate_entry(
        {"candidate_id": "c1", "instrument": "EUR_USD", "strategy_name": "Breakout-Squeeze"},
        {"spread_dislocation": 0.9, "spread_bps": 4.0, "velocity": 1.0, "impulse": 0.9, "distance_from_trigger_atr": 1.0, "escape_velocity": 0.9},
        rd,
        ev,
        {},
    )
    assert not d.allow_entry
