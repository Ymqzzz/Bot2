from __future__ import annotations

from .settings import BotSettings


def validate_settings(settings: BotSettings) -> None:
    if not settings.instruments:
        raise ValueError("settings.instruments cannot be empty")
    if settings.min_signal_score < 0:
        raise ValueError("min_signal_score must be >= 0")
    if settings.max_spread_pctile <= 0 or settings.max_spread_pctile > 100:
        raise ValueError("max_spread_pctile must be in (0, 100]")
    if settings.max_positions < 1:
        raise ValueError("max_positions must be >= 1")
    if settings.risk_budget_daily <= 0:
        raise ValueError("risk_budget_daily must be positive")
