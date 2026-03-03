from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
import math
import numpy as np


CLUSTER_MAP = {
    "USD_BLOC": {"EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD", "USD_CHF", "USD_CAD", "USD_JPY", "USD_NOK", "USD_SEK", "USD_SGD"},
    "JPY_CROSSES": {"USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY", "NZD_JPY", "CAD_JPY"},
    "EUR_BLOC": {"EUR_USD", "EUR_GBP", "EUR_CHF", "EUR_AUD", "EUR_CAD", "EUR_NZD", "EUR_JPY"},
    "COMMODITY_FX": {"AUD_USD", "NZD_USD", "USD_CAD", "AUD_CAD", "NZD_CHF", "AUD_CHF"},
}


@dataclass
class PortfolioLimits:
    max_net_ccy_exposure_pct: float = 0.30
    max_gross_ccy_exposure_pct: float = 0.80
    daily_risk_pct: float = 0.015
    max_cluster_risk_pct: float = 0.010
    corr_threshold: float = 0.72



def pair_currencies(instr: str) -> Tuple[str, str]:
    base, quote = instr.split("_")
    return base, quote


def currency_exposure_matrix(positions: List[Dict]) -> Dict[str, Dict[str, float]]:
    net = {}
    gross = {}
    for p in positions:
        instr = p.get("instrument", "")
        units = float(p.get("units", 0.0))
        if "_" not in instr:
            continue
        base, quote = pair_currencies(instr)
        net[base] = net.get(base, 0.0) + units
        net[quote] = net.get(quote, 0.0) - units
        gross[base] = gross.get(base, 0.0) + abs(units)
        gross[quote] = gross.get(quote, 0.0) + abs(units)
    return {"net": net, "gross": gross}


def estimate_risk_cost(entry: float, stop_loss: float, units: float, nav: float, corr_penalty: float = 1.0) -> float:
    risk_value = abs(entry - stop_loss) * abs(units)
    return (risk_value / max(nav, 1e-9)) * max(1.0, corr_penalty)


def cluster_for_instrument(instr: str) -> str:
    for cluster, members in CLUSTER_MAP.items():
        if instr in members:
            return cluster
    return "OTHER"


def correlation_penalty(instr: str, open_positions: List[Dict], corr_matrix: Dict[str, Dict[str, float]], threshold: float) -> float:
    vals = []
    for p in open_positions:
        j = p.get("instrument")
        if not j or j == instr:
            continue
        c = abs(float((corr_matrix.get(instr) or {}).get(j, 0.0)))
        if c > threshold:
            vals.append(c)
    if not vals:
        return 1.0
    return 1.0 + min(0.8, float(np.mean(vals)) - threshold)


def apply_portfolio_caps(proposal: Dict, open_positions: List[Dict], nav: float, corr_matrix: Dict[str, Dict[str, float]], limits: PortfolioLimits) -> Dict:
    positions = list(open_positions)
    trial_position = {"instrument": proposal["instrument"], "units": proposal.get("signed_units", 0)}
    positions.append(trial_position)
    expo = currency_exposure_matrix(positions)

    # Compare exposures against account size instead of exposure-share-of-exposure.
    # In FX every position creates two offsetting currency legs, so share-based
    # normalization (sum(abs(net))) makes the largest currency share >= 0.5 and
    # can trivially block every proposal with realistic caps such as 0.30-0.40.
    nav_denom = max(float(nav), 1e-9)
    worst_net = max([abs(v) / nav_denom for v in expo["net"].values()] + [0.0])
    worst_gross = max([abs(v) / nav_denom for v in expo["gross"].values()] + [0.0])

    cluster = cluster_for_instrument(proposal["instrument"])
    corr_pen = correlation_penalty(proposal["instrument"], open_positions, corr_matrix, limits.corr_threshold)
    risk_cost = estimate_risk_cost(proposal["entry_price"], proposal["stop_loss"], proposal.get("signed_units", 0), nav, corr_pen)

    out = dict(proposal)
    out["correlation_cluster_id"] = cluster
    out["risk_cost"] = risk_cost

    if worst_net > limits.max_net_ccy_exposure_pct:
        out["blocked"] = True
        out["block_reason"] = f"net_exposure_cap:{worst_net:.3f}"
    elif worst_gross > limits.max_gross_ccy_exposure_pct:
        out["blocked"] = True
        out["block_reason"] = f"gross_exposure_cap:{worst_gross:.3f}"
    elif risk_cost > limits.daily_risk_pct:
        out["blocked"] = True
        out["block_reason"] = f"risk_budget:{risk_cost:.4f}"
    else:
        out["blocked"] = False
        out["block_reason"] = ""

    out["exposure_snapshot"] = {"net": expo["net"], "gross": expo["gross"], "worst_net": worst_net, "worst_gross": worst_gross}
    return out


def select_portfolio_subset(proposals: List[Dict], max_positions: int, risk_budget: float, cluster_cap: float) -> List[Dict]:
    ranked = sorted(proposals, key=lambda p: p.get("expected_value_proxy", p.get("ev_r", 0.0)), reverse=True)
    selected = []
    used_risk = 0.0
    cluster_risk = {}
    for p in ranked:
        if p.get("blocked"):
            continue
        rc = float(p.get("risk_cost", 0.0))
        cluster = p.get("correlation_cluster_id", "OTHER")
        if used_risk + rc > risk_budget:
            continue
        if cluster_risk.get(cluster, 0.0) + rc > cluster_cap:
            continue
        selected.append(p)
        used_risk += rc
        cluster_risk[cluster] = cluster_risk.get(cluster, 0.0) + rc
        if len(selected) >= max_positions:
            break
    return selected
