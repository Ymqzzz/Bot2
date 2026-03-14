from __future__ import annotations

from dataclasses import dataclass

from portfolio_risk import PortfolioLimits, apply_portfolio_caps


@dataclass
class PortfolioContext:
    open_positions: list[dict]
    nav: float
    corr_matrix: dict


def apply_caps(candidate: dict, ctx: PortfolioContext, daily_risk_pct: float, cluster_risk_pct: float) -> dict:
    limits = PortfolioLimits(daily_risk_pct=daily_risk_pct, max_cluster_risk_pct=cluster_risk_pct)
    return apply_portfolio_caps(candidate, ctx.open_positions, ctx.nav, ctx.corr_matrix, limits)
