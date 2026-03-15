from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os


class ReplayStepGranularity(str, Enum):
    TICK = "tick"
    SECOND = "second"
    BAR_CLOSE = "bar_close"


class CalibrationMethod(str, Enum):
    ISOTONIC = "isotonic"
    PLATT = "platt"
    BINNED = "binned"


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class ResearchCoreConfig:
    RESEARCH_CORE_ENABLED: bool = _env_bool("RESEARCH_CORE_ENABLED", True)
    RESEARCH_CORE_STORAGE_ENABLED: bool = _env_bool("RESEARCH_CORE_STORAGE_ENABLED", True)

    REPLAY_ENABLED: bool = _env_bool("REPLAY_ENABLED", True)
    REPLAY_STEP_GRANULARITY: ReplayStepGranularity = ReplayStepGranularity(os.environ.get("REPLAY_STEP_GRANULARITY", "bar_close"))
    REPLAY_ALLOW_DEGRADED_INPUTS: bool = _env_bool("REPLAY_ALLOW_DEGRADED_INPUTS", True)
    REPLAY_MAX_DIVERGENCE_WARNINGS: int = int(os.environ.get("REPLAY_MAX_DIVERGENCE_WARNINGS", "250"))

    SIMULATION_ENABLED: bool = _env_bool("SIMULATION_ENABLED", True)
    SIMULATION_PARALLEL_SCENARIOS: int = int(os.environ.get("SIMULATION_PARALLEL_SCENARIOS", "1"))
    SIMULATION_MAX_VARIANTS: int = int(os.environ.get("SIMULATION_MAX_VARIANTS", "10"))
    SIMULATION_INCLUDE_TRANSACTION_COSTS: bool = _env_bool("SIMULATION_INCLUDE_TRANSACTION_COSTS", True)
    SIMULATION_INCLUDE_SLIPPAGE_MODEL: bool = _env_bool("SIMULATION_INCLUDE_SLIPPAGE_MODEL", True)
    SIMULATION_INCLUDE_PARTIAL_FILLS: bool = _env_bool("SIMULATION_INCLUDE_PARTIAL_FILLS", True)

    CALIBRATION_ENABLED: bool = _env_bool("CALIBRATION_ENABLED", True)
    CALIBRATION_METHOD: CalibrationMethod = CalibrationMethod(os.environ.get("CALIBRATION_METHOD", "binned"))
    CALIBRATION_MIN_SAMPLE_SIZE: int = int(os.environ.get("CALIBRATION_MIN_SAMPLE_SIZE", "30"))
    CALIBRATION_REFRESH_TRADES: int = int(os.environ.get("CALIBRATION_REFRESH_TRADES", "50"))
    CALIBRATION_SCOPE_STRATEGY: bool = _env_bool("CALIBRATION_SCOPE_STRATEGY", True)
    CALIBRATION_SCOPE_INSTRUMENT: bool = _env_bool("CALIBRATION_SCOPE_INSTRUMENT", True)
    CALIBRATION_SCOPE_SESSION: bool = _env_bool("CALIBRATION_SCOPE_SESSION", True)
    CALIBRATION_SCOPE_REGIME: bool = _env_bool("CALIBRATION_SCOPE_REGIME", True)
    CALIBRATION_SCOPE_SETUP_TYPE: bool = _env_bool("CALIBRATION_SCOPE_SETUP_TYPE", True)
    CALIBRATION_FALLBACK_GLOBAL: bool = _env_bool("CALIBRATION_FALLBACK_GLOBAL", True)
    CALIBRATION_NUM_BINS: int = int(os.environ.get("CALIBRATION_NUM_BINS", "10"))

    META_APPROVAL_ENABLED: bool = _env_bool("META_APPROVAL_ENABLED", True)
    META_APPROVAL_MIN_SCORE: float = float(os.environ.get("META_APPROVAL_MIN_SCORE", "0.55"))
    META_APPROVAL_MIN_CALIBRATED_WIN_PROB: float = float(os.environ.get("META_APPROVAL_MIN_CALIBRATED_WIN_PROB", "0.48"))
    META_APPROVAL_MIN_EXPECTANCY_PROXY: float = float(os.environ.get("META_APPROVAL_MIN_EXPECTANCY_PROXY", "0.0"))
    META_APPROVAL_REJECT_IF_UNCALIBRATED: bool = _env_bool("META_APPROVAL_REJECT_IF_UNCALIBRATED", False)
    META_APPROVAL_ALLOW_DELAY_MODE: bool = _env_bool("META_APPROVAL_ALLOW_DELAY_MODE", True)
    META_APPROVAL_DEFAULT_DELAY_SECONDS: int = int(os.environ.get("META_APPROVAL_DEFAULT_DELAY_SECONDS", "30"))
    META_APPROVAL_DOWNSIZE_MULTIPLIER: float = float(os.environ.get("META_APPROVAL_DOWNSIZE_MULTIPLIER", "0.5"))
    META_APPROVAL_HARD_REJECT_ON_EVENT_CONFLICT: bool = _env_bool("META_APPROVAL_HARD_REJECT_ON_EVENT_CONFLICT", True)
    META_APPROVAL_HARD_REJECT_ON_EXECUTION_DISLOCATION: bool = _env_bool("META_APPROVAL_HARD_REJECT_ON_EXECUTION_DISLOCATION", True)

    REPORTS_ENABLED: bool = _env_bool("REPORTS_ENABLED", True)
    REPORTS_OUTPUT_DIR: str = os.environ.get("REPORTS_OUTPUT_DIR", "research_outputs")

    def validate(self) -> None:
        if self.REPLAY_MAX_DIVERGENCE_WARNINGS < 0:
            raise ValueError("REPLAY_MAX_DIVERGENCE_WARNINGS must be >=0")
        if self.SIMULATION_PARALLEL_SCENARIOS < 1:
            raise ValueError("SIMULATION_PARALLEL_SCENARIOS must be >=1")
        if self.SIMULATION_MAX_VARIANTS < 1:
            raise ValueError("SIMULATION_MAX_VARIANTS must be >=1")
        if self.CALIBRATION_MIN_SAMPLE_SIZE < 5:
            raise ValueError("CALIBRATION_MIN_SAMPLE_SIZE must be >=5")
        if self.CALIBRATION_NUM_BINS < 2:
            raise ValueError("CALIBRATION_NUM_BINS must be >=2")
        if not (0 <= self.META_APPROVAL_DOWNSIZE_MULTIPLIER <= 1):
            raise ValueError("META_APPROVAL_DOWNSIZE_MULTIPLIER must be in [0,1]")


def load_config() -> ResearchCoreConfig:
    config = ResearchCoreConfig()
    config.validate()
    return config
