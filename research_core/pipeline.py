from __future__ import annotations

from datetime import datetime

from research_core.calibration import ConfidenceCalibrator
from research_core.config import ResearchCoreConfig
from research_core.experiment_runner import ExperimentRunner
from research_core.meta_approval import MetaApprovalEngine
from research_core.meta_features import build_meta_feature_snapshot
from research_core.replay_lab import ReplayLab
from research_core.simulator import Simulator
from research_core.storage import ResearchStorage


class ResearchCorePipeline:
    def __init__(self, config: ResearchCoreConfig, replay_loader):
        self.config = config
        self.storage = ResearchStorage(base_dir=config.REPORTS_OUTPUT_DIR)
        self.replay_lab = ReplayLab(replay_loader)
        self.simulator = Simulator(self.replay_lab)
        self.experiment_runner = ExperimentRunner(self.simulator)
        self.calibrator = ConfidenceCalibrator(config)
        self.meta_engine = MetaApprovalEngine(config)

    def run_replay(self, start_ts: datetime, end_ts: datetime, instruments: list[str], scenario=None):
        result = self.replay_lab.run_replay(start_ts, end_ts, instruments, scenario)
        self.storage.append_jsonl("replay_results", result.to_flat_dict())
        return result

    def run_simulation_set(self, start_ts: datetime, end_ts: datetime, instruments: list[str], scenarios):
        run = self.experiment_runner.run_experiment_set(start_ts, end_ts, instruments, scenarios)
        self.storage.append_jsonl("simulation_runs", run.to_flat_dict())
        return run

    def refresh_calibration(self, historical_records: list[dict], force: bool = False):
        snapshots = self.calibrator.refresh_if_needed(historical_records, force=force)
        for snapshot in snapshots:
            self.storage.append_jsonl("calibration_snapshots", snapshot.to_flat_dict())
        return snapshots

    def build_meta_features(self, candidate: dict, context: dict):
        return build_meta_feature_snapshot(candidate, context)

    def meta_approve_candidate(self, candidate: dict, context: dict):
        features = self.build_meta_features(candidate, context)
        decision = self.meta_engine.evaluate_candidate(candidate, features, context)
        self.storage.append_jsonl("meta_feature_snapshots", features.to_flat_dict())
        self.storage.append_jsonl("meta_approval_decisions", decision.to_flat_dict())
        return decision
