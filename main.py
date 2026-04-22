from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
import importlib
import math
import os
from statistics import NormalDist, fmean, pstdev
import time
from typing import Any

import pandas as pd

from app.runtime.adapters import (
    ControlPlaneLifecycleAdapter,
    ResearchCoreLifecycleAdapter,
    TradeIntelLifecycleAdapter,
)
from app.runtime.engine import JsonlEventAuditStore, RuntimeCoordinator, RuntimeCycleInput, RuntimeSnapshot


INSTRUMENTS: list[str] = ["EUR_USD", "USD_JPY", "GBP_USD"]
TRADE_HARD_MAX = 10
MIN_PLAN_RR = 1.2
MIN_PLAN_EVR = 0.2

daily_trade_budget: dict[str, int] = {"trades_opened_today": 0}
spread_cache: dict[str, float] = {}
spread_history: defaultdict[str, list[tuple[float, float]]] = defaultdict(list)
strategy_return_history: deque[float] = deque(maxlen=252)

DEFAULT_STARTUP_MODULES: tuple[str, ...] = (
    "dashboard",
    "ui_dashboard",
    "execution_engine",
    "lifecycle_manager",
    "portfolio_risk",
    "world_state",
    "reporting",
    "edge_health",
    "director_llm",
)

_startup_modules_loaded = False


def _configured_startup_modules() -> tuple[str, ...]:
    raw = (os.getenv("STARTUP_MODULES", "") or "").strip()
    if not raw:
        return DEFAULT_STARTUP_MODULES
    modules = tuple(entry.strip() for entry in raw.split(",") if entry.strip())
    return modules or DEFAULT_STARTUP_MODULES


def run_startup_initializers() -> None:
    """Import configured modules once so standalone utilities are initialized at boot."""
    global _startup_modules_loaded
    if _startup_modules_loaded:
        return
    for module_name in _configured_startup_modules():
        importlib.import_module(module_name)
    _startup_modules_loaded = True


def safe_get(*_args, **_kwargs):
    return None


def get_candles(_instrument: str, count: int = 200, granularity: str = "M5") -> pd.DataFrame | None:
    payload = safe_get("candles", instrument=_instrument, count=count, granularity=granularity)
    if not payload:
        return None
    rows = []
    for c in payload.get("candles", []):
        if not c.get("complete"):
            continue
        mid = c.get("mid") or {}
        rows.append(
            {
                "time": c.get("time"),
                "o": float(mid.get("o", 0.0)),
                "h": float(mid.get("h", 0.0)),
                "l": float(mid.get("l", 0.0)),
                "c": float(mid.get("c", 0.0)),
                "v": int(c.get("volume", 0)),
            }
        )
    return pd.DataFrame(rows, columns=["time", "o", "h", "l", "c", "v"]) if rows else pd.DataFrame(columns=["time", "o", "h", "l", "c", "v"])


def session_label(dt: datetime) -> str:
    h = dt.astimezone(timezone.utc).hour
    if h < 7:
        return "ASIA"
    if h < 12:
        return "LONDON"
    if h < 17:
        return "OVERLAP"
    if h < 22:
        return "NY"
    return "DEAD_ZONE"


def higher_tf_alignment(instrument: str) -> float:
    votes = []
    for tf in ("H1", "M15"):
        df = get_candles(instrument, count=300, granularity=tf)
        if df is None or len(df) < 2:
            continue
        first = float(df.iloc[0]["c"])
        last = float(df.iloc[-1]["c"])
        votes.append(1.0 if last > first else -1.0)
    if not votes:
        return 0.0
    s = sum(votes)
    if s > 0:
        return 1.0
    if s < 0:
        return -1.0
    return 0.0


def garman_kohlhagen(S: float, K: float, T: float, sigma: float, rd: float, rf: float, call: bool = True) -> dict[str, float]:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {"price": 0.0, "delta": 0.0, "gamma": 0.0}
    vol_sqrt_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (rd - rf + 0.5 * sigma * sigma) * T) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    n = NormalDist()
    nd1 = n.cdf(d1)
    nd2 = n.cdf(d2)
    nmd1 = n.cdf(-d1)
    nmd2 = n.cdf(-d2)
    disc_f = math.exp(-rf * T)
    disc_d = math.exp(-rd * T)
    if call:
        price = S * disc_f * nd1 - K * disc_d * nd2
        delta = disc_f * nd1
    else:
        price = K * disc_d * nmd2 - S * disc_f * nmd1
        delta = -disc_f * nmd1
    gamma = (disc_f * n.pdf(d1)) / (S * vol_sqrt_t)
    return {"price": float(price), "delta": float(delta), "gamma": float(gamma)}


def spread_liquidity_guard(instrument: str, stale_after_sec: float = 5.0) -> tuple[bool, dict[str, Any]]:
    now = time.time()
    hist = spread_history.get(instrument, [])
    stale = (not hist) or ((now - hist[-1][0]) > stale_after_sec)
    percentile = 100.0 if stale else 50.0
    return stale, {"stale": stale, "percentile": percentile}


def spread_percentile_guard(instrument: str) -> tuple[bool, dict[str, Any]]:
    blocked, info = spread_liquidity_guard(instrument)
    return blocked, info


def liquidity_factor(instrument: str) -> float:
    hist = spread_history.get(instrument, [])
    if not hist:
        return 0.5 if spread_cache.get(instrument) else 0.0
    return 1.0


def strategy_enabled(_name: str) -> bool:
    return True


def candidate_plans_from_snapshot(_snapshot: dict[str, Any], allowed_impl=None) -> list[dict[str, Any]]:
    _ = allowed_impl
    return []


def plan_passes_gates(plan: dict[str, Any], snapshot: dict[str, Any]) -> tuple[bool, str]:
    if daily_trade_budget.get("trades_opened_today", 0) >= TRADE_HARD_MAX:
        return False, "Budget"
    if snapshot.get("event_block"):
        return False, "Event"
    if snapshot.get("spread_block"):
        return False, "Spread"
    if float(plan.get("rr", 0.0) or 0.0) < MIN_PLAN_RR:
        return False, "RR"
    if float(plan.get("ev_r", 0.0) or 0.0) < MIN_PLAN_EVR:
        return False, "EV"
    return True, "OK"


def strategy_router(instrument: str, snapshot: dict[str, Any]):
    candidates = [p for p in candidate_plans_from_snapshot(snapshot) if strategy_enabled(str(p.get("strategy", "")))]
    ranked = []
    for plan in candidates:
        ok, reason = plan_passes_gates(plan, snapshot)
        if not ok:
            continue
        rank = float(plan.get("ev_r", 0.0)) * float(plan.get("confidence", 0.0))
        rank *= 1.0 + max(0.0, float(snapshot.get("liq_factor", 0.0)) - 0.5)
        mode = str(snapshot.get("mode", "")).lower()
        strategy = str(plan.get("strategy", "")).lower()
        if "trend" in mode and "range" in strategy:
            rank *= 0.8
        plan_with_rank = dict(plan)
        plan_with_rank["rank"] = rank
        plan_with_rank["gate_reason"] = reason
        ranked.append(plan_with_rank)
    ranked.sort(key=lambda p: p["rank"], reverse=True)
    return (ranked[0] if ranked else None), ranked


def reset_daily_trade_budget_if_needed() -> None:
    return None


def refresh_pricing_once() -> None:
    return None


def get_nav() -> tuple[float, str]:
    return 0.0, "USD"


def get_positions_info() -> list[dict[str, Any]]:
    return []


def portfolio_var(*_args, **_kwargs) -> dict[str, float]:
    return {"param": 0.0}


def current_portfolio_heat(_nav: float) -> float:
    return 0.0


def currency_exposure_map() -> dict[str, float]:
    return {}


def compute_day_realized_pnl() -> float:
    return 0.0


def strategy_sharpe() -> float:
    returns = list(strategy_return_history)
    if len(returns) < 2:
        return 0.0
    risk_free_daily = 0.02 / 252.0
    excess = [r - risk_free_daily for r in returns]
    vol = pstdev(excess)
    if vol <= 1e-9:
        return 0.0
    annualized = (fmean(excess) / vol) * math.sqrt(252.0)
    # Shrink toward zero when sample size is small to avoid unstable estimates.
    sample_weight = min(1.0, len(returns) / 63.0)
    return float(annualized * sample_weight)


def build_market_snapshot(instrument: str) -> dict[str, Any]:
    return {"instrument": instrument}


def build_world_state(top_n: int = 5) -> dict[str, Any]:
    reset_daily_trade_budget_if_needed()
    refresh_pricing_once()
    nav, base_ccy = get_nav()
    market = {}
    for instrument in INSTRUMENTS[:top_n]:
        snap = build_market_snapshot(instrument)
        market[instrument] = {"snapshot": snap}
    return {
        "account": {
            "nav": nav,
            "base_ccy": base_ccy,
            "positions": get_positions_info(),
            "portfolio_var": portfolio_var(market),
            "portfolio_heat": current_portfolio_heat(nav),
            "currency_exposure": currency_exposure_map(),
            "day_realized_pnl": compute_day_realized_pnl(),
            "strategy_sharpe": strategy_sharpe(),
        },
        "market": market,
    }


class RuntimeBootstrap:
    """Thin runtime bootstrap wrapper.

    Responsibilities:
    - load module configs
    - wire provider/pipeline dependencies
    - delegate orchestration to RuntimeCoordinator
    """

    def __init__(self) -> None:
        from control_plane import ControlPlanePipeline, load_config as load_control_plane_config
        from trade_intel import build_default_pipeline, load_config as load_trade_intel_config
        from research_core import ResearchCorePipeline, load_config as load_research_core_config

        control_plane_pipeline = ControlPlanePipeline(load_control_plane_config())
        trade_intel_pipeline = build_default_pipeline(load_trade_intel_config())

        research_cfg = load_research_core_config()
        research_pipeline = None
        if research_cfg.RESEARCH_CORE_ENABLED:

            def _empty_loader(*_args, **_kwargs):
                raise RuntimeError("Replay loader is not available in runtime bootstrap")

            research_pipeline = ResearchCorePipeline(research_cfg, replay_loader=_empty_loader)

        self.coordinator = RuntimeCoordinator(
            control_plane=ControlPlaneLifecycleAdapter(control_plane_pipeline),
            trade_intel=TradeIntelLifecycleAdapter(trade_intel_pipeline),
            research_core=ResearchCoreLifecycleAdapter(research_pipeline),
            store=JsonlEventAuditStore(self._persist_cycle_event),
        )

    def _persist_cycle_event(self, payload: dict[str, Any]) -> None:
        _ = payload

    def run_cycle(
        self,
        instruments: list[str],
        market_data: dict[str, Any],
        bars: dict[str, Any],
        open_positions: list[dict[str, Any]],
        candidate_pool: list[dict[str, Any]],
        snapshot: RuntimeSnapshot | None = None,
        context: dict[str, Any] | None = None,
    ):
        runtime_snapshot = snapshot or RuntimeSnapshot(timestamp=datetime.now(timezone.utc))
        runtime_input = RuntimeCycleInput(
            instruments=instruments,
            market_data=market_data,
            bars=bars,
            open_positions=open_positions,
            context={"candidate_pool": candidate_pool, **(context or {})},
        )
        return self.coordinator.run_cycle(runtime_input, runtime_snapshot)


def build_runtime() -> RuntimeBootstrap:
    run_startup_initializers()
    return RuntimeBootstrap()
