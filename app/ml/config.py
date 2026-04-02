from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


RLModeLiteral = Literal["shadow", "advisory", "active"]


@dataclass(frozen=True)
class PPOConfig:
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    ent_coef: float = 0.01
    clip_range: float = 0.2
    batch_size: int = 64
    n_steps: int = 512
    net_arch: tuple[int, ...] = (128, 128)
    max_grad_norm: float = 0.5


@dataclass(frozen=True)
class RewardWeights:
    pnl: float = 1.0
    risk_adjusted: float = 0.5
    execution_quality: float = 0.3
    signal_quality: float = 0.25
    transaction_cost: float = 1.0
    slippage: float = 1.0
    drawdown: float = 1.2
    overtrading: float = 0.2
    tail_risk: float = 0.8
    regime_mismatch: float = 0.25


@dataclass(frozen=True)
class MLConfig:
    mode: RLModeLiteral = "shadow"
    model_root: Path = Path("research_outputs/ml_models")
    registry_path: Path = Path("research_outputs/ml_models/registry.json")
    replay_store_path: Path = Path("research_outputs/ml_models/replay.jsonl")
    telemetry_dir: Path = Path("research_outputs/ml_telemetry")
    latency_budget_ms: int = 50
    min_confidence: float = 0.55
    max_entropy: float = 1.5
    allow_ood_influence: bool = False
    drift_psi_threshold: float = 0.3
    ppo: PPOConfig = field(default_factory=PPOConfig)
    reward_weights: RewardWeights = field(default_factory=RewardWeights)


DEFAULT_ML_CONFIG = MLConfig()
