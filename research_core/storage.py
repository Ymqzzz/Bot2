from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


class ResearchStorage:
    def __init__(self, base_dir: str = "research_outputs", sqlite_path: str | None = None):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = sqlite_path
        if sqlite_path:
            self._ensure_sqlite()

    def append_jsonl(self, name: str, payload: dict[str, Any]) -> str:
        path = self.base_dir / f"{name}.jsonl"
        row = dict(payload)
        row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        path.write_text((path.read_text() if path.exists() else "") + json.dumps(row) + "\n")
        return str(path)

    def _ensure_sqlite(self) -> None:
        conn = sqlite3.connect(self.sqlite_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS research_replay_results (replay_id TEXT PRIMARY KEY, start_ts TEXT, end_ts TEXT, instruments_json TEXT, num_steps INTEGER, num_candidates INTEGER, num_approved INTEGER, num_rejected INTEGER, num_executed INTEGER, num_closed_trades INTEGER, gross_pnl REAL, net_pnl REAL, net_r REAL, max_drawdown_r REAL, approval_rate REAL, divergence_flags_json TEXT, reason_codes_json TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS research_replay_step_records (id INTEGER PRIMARY KEY AUTOINCREMENT, replay_id TEXT, step_ts TEXT, instrument TEXT, market_intel_ref TEXT, trade_intel_ref TEXT, control_plane_ref TEXT, candidate_ids_json TEXT, approved_candidate_ids_json TEXT, blocked_candidate_ids_json TEXT, meta_decision_ids_json TEXT, execution_outcomes_json TEXT, open_positions_snapshot_json TEXT, portfolio_state_snapshot_json TEXT, warnings_json TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS research_calibration_snapshots (calibration_id TEXT PRIMARY KEY, scope_type TEXT, scope_key TEXT, sample_size INTEGER, calibration_method TEXT, reliability_score REAL, brier_score REAL, ece_score REAL, mce_score REAL, bins_json TEXT, mapping_params_json TEXT, fresh_asof TEXT, reason_codes_json TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS research_meta_approval_decisions (decision_id TEXT PRIMARY KEY, candidate_id TEXT, instrument TEXT, strategy_name TEXT, action TEXT, approval_score REAL, calibrated_win_prob REAL, calibrated_expectancy_proxy REAL, risk_adjustment_multiplier REAL, delay_seconds INTEGER, reject INTEGER, reject_hard INTEGER, reason_codes_json TEXT, diagnostics_json TEXT, created_at TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS research_simulation_runs (simulation_id TEXT PRIMARY KEY, baseline_scenario_json TEXT, variant_scenarios_json TEXT, start_ts TEXT, end_ts TEXT, results_by_scenario_json TEXT, comparisons_json TEXT, reason_codes_json TEXT)")
        conn.commit()
        conn.close()
