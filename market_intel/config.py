from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for market intel build behavior."""

    strict_mode: bool = False
    strict_dependencies: Set[str] = field(default_factory=set)
    timeout_ms: int = 200
    provider_kwargs: Dict[str, dict] = field(default_factory=dict)
