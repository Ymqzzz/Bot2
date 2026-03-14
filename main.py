# ========== IMPORTS ==========
import asyncio
import hashlib
import json
import logging
import math
import os
import statistics
import sys
import time

import requests
import pandas as pd
import numpy as np
import discord
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from discord.ext import commands
from flask import Flask, render_template_string, request, jsonify
from threading import Thread
from collections import deque, defaultdict
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
from sklearn.ensemble import GradientBoostingRegressor

from portfolio_risk import PortfolioLimits, apply_portfolio_caps
from execution_engine import ExecutionStats, choose_entry_type, clip_staging_plan
from edge_health import EdgeHealthMonitor
from world_state import session_playbook
from reporting import write_eod_report
from trade_intel import load_config as load_trade_intel_config
from trade_intel.pipeline import build_default_pipeline


# ========= CONFIG =========
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
OANDA_API_KEY = os.environ.get("OANDA_API_KEY", "")
OANDA_ACCOUNTID = os.environ.get("OANDA_ACCOUNTID", "")
# Add to your config section
# Add these missing config variables:
SHARPE_FLOOR = float(os.environ.get("SHARPE_FLOOR", "-0.50"))  # Sharpe gate floor
DISCORD_ADMIN_PIN = os.environ.get("DISCORD_ADMIN_PIN", "")    # optional admin PIN for !auth
USE_ML = True
USE_KMEANS_REGIME = True
# Your existing config continues...
if os.environ.get("INSTRUMENTS_JSON"):
    INSTRUMENTS = json.loads(os.environ["INSTRUMENTS_JSON"])
else:
    INSTRUMENTS = [
        "EUR_USD","USD_JPY","GBP_USD","AUD_USD","USD_CHF","USD_CAD","NZD_USD",
        "USD_SEK","USD_NOK","USD_SGD",
        "EUR_JPY","EUR_GBP","EUR_CHF","EUR_AUD","EUR_CAD","EUR_NZD",
        "GBP_JPY","GBP_CHF","GBP_AUD","GBP_CAD",
        "AUD_JPY","AUD_CHF","AUD_CAD","CAD_JPY",
        "NZD_JPY","NZD_CHF"
    ]  # expanded default universe for broader signal ingestion

GRANULARITY  = os.environ.get("GRANULARITY", "M5")
COOLDOWN_SEC = int(os.environ.get("COOLDOWN_SEC", "5"))
AUTO_TRADE_ON_FLAG = True  # keeps original AUTO_TRADE_ON behavior
# Analysis log config
LOG_MAX = int(os.environ.get("LOG_MAX", "1000"))        # max events kept in memory
LOG_VERBOSITY = int(os.environ.get("LOG_VERBOSITY", "2"))  # 0=quiet, 1=basic, 2=detailed, 3=trace
# ==== Breakout / Compression params ====
DONCHIAN_N = int(os.environ.get("DONCHIAN_N", "40"))      # breakout lookback
BBANDS_N   = int(os.environ.get("BBANDS_N", "20"))        # Bollinger lookback
SQUEEZE_Q  = float(os.environ.get("SQUEEZE_Q", "0.20"))   # percentile for "compression" (0.2 = bottom 20%)
MIN_COMPRESSION_SCORE = float(os.environ.get("MIN_COMPRESSION_SCORE", "0.65"))  # gate

# Indicators / model params
EMA_FAST   = int(os.environ.get("EMA_FAST", "10"))
EMA_SLOW   = int(os.environ.get("EMA_SLOW", "30"))
EMA_PERIOD = int(os.environ.get("EMA_PERIOD", "20"))
ATR_PERIOD = int(os.environ.get("ATR_PERIOD", "14"))
ZS_LOOKBACK = int(os.environ.get("ZS_LOOKBACK", "200"))
CACHE_TTL  = int(os.environ.get("CACHE_TTL", "10"))
JB_LOOKBACK = int(os.environ.get("JB_LOOKBACK", "400"))

# Risk
ACCOUNT_RISK_PCT = float(os.environ.get("ACCOUNT_RISK_PCT", "0.005"))     # 0.5%/trade
TARGET_ANNUAL_VOL = float(os.environ.get("TARGET_ANNUAL_VOL", "0.10"))
MAX_LEVERAGE = float(os.environ.get("MAX_LEVERAGE", "5.0"))
MIN_EDGE_MULT_COST = float(os.environ.get("MIN_EDGE_MULT_COST", "1.5"))
MAX_POSITIONS_PER_INSTR = int(os.environ.get("MAX_POSITIONS_PER_INSTR", "5"))
VAR_LIMIT_PCT = float(os.environ.get("VAR_LIMIT_PCT", "0.02"))            # 1d 99% VaR cap
MAX_CCY_RISK_SHARE = float(os.environ.get("MAX_CCY_RISK_SHARE", "0.30"))
MAX_USD_CLUSTER_SHARE = float(os.environ.get("MAX_USD_CLUSTER_SHARE", "0.55"))
MAX_TOTAL_HEAT = float(os.environ.get("MAX_TOTAL_HEAT", "0.04"))
MAX_NET_CCY_EXPOSURE_PCT = float(os.environ.get("MAX_NET_CCY_EXPOSURE_PCT", "0.35"))
MAX_GROSS_CCY_EXPOSURE_PCT = float(os.environ.get("MAX_GROSS_CCY_EXPOSURE_PCT", "0.85"))
DAILY_RISK_PCT = float(os.environ.get("DAILY_RISK_PCT", "0.015"))
RISK_PARITY_VOL_WINDOW = int(os.environ.get("RISK_PARITY_VOL_WINDOW", "120"))
ORDERFLOW_TTL = int(os.environ.get("ORDERFLOW_TTL", "20"))

# Enrichment TTLs / windows
MACRO_TTL = int(os.environ.get("MACRO_TTL", "60"))
ECON_TTL  = int(os.environ.get("ECON_TTL",  "300"))
COT_TTL   = int(os.environ.get("COT_TTL",   "21600"))
CORR_WIN  = int(os.environ.get("CORR_WIN",  "45"))   # bars
EVENT_WINDOW_MIN = int(os.environ.get("EVENT_WINDOW_MIN", "10"))
EVENT_PRE_BUFFER_MIN = int(os.environ.get("EVENT_PRE_BUFFER_MIN", "20"))
EVENT_POST_BUFFER_MIN = int(os.environ.get("EVENT_POST_BUFFER_MIN", "20"))

# Trading upgrade pack controls
SPREAD_GUARD_PCTL = float(os.environ.get("SPREAD_GUARD_PCTL", "95"))
ATR_SPIKE_MULT = float(os.environ.get("ATR_SPIKE_MULT", "1.8"))
IDEA_DEDUP_BARS = int(os.environ.get("IDEA_DEDUP_BARS", "6"))
SIGNAL_ID_TTL_MIN = int(os.environ.get("SIGNAL_ID_TTL_MIN", "45"))
PORTFOLIO_HEAT_LIMIT = float(os.environ.get("PORTFOLIO_HEAT_LIMIT", "0.015"))
CLUSTER_HEAT_LIMIT = float(os.environ.get("CLUSTER_HEAT_LIMIT", "0.009"))
DAILY_LOSS_LIMIT_PCT = float(os.environ.get("DAILY_LOSS_LIMIT_PCT", "0.02"))
DAILY_DD_KILL_PCT = float(os.environ.get("DAILY_DD_KILL_PCT", "0.015"))
TIME_STOP_BARS = int(os.environ.get("TIME_STOP_BARS", "18"))
RISK_CUTOFF_EXPECTANCY_TRADES = int(os.environ.get("RISK_CUTOFF_EXPECTANCY_TRADES", "30"))
MIN_PLAN_RR = float(os.environ.get("MIN_PLAN_RR", "1.25"))
MIN_PLAN_EVR = float(os.environ.get("MIN_PLAN_EVR", "0.05"))
STRAT_DISABLE_COOLDOWN_MIN = int(os.environ.get("STRAT_DISABLE_COOLDOWN_MIN", "1440"))
PARTIAL_CLOSE_FRACTION = float(os.environ.get("PARTIAL_CLOSE_FRACTION", "0.4"))
TIME_STOP_PROGRESS_R = float(os.environ.get("TIME_STOP_PROGRESS_R", "0.5"))

# Director / quota / OpenRouter controls
TRADE_TARGET_MIN = int(os.environ.get("TRADE_TARGET_MIN", "2"))
TRADE_TARGET_MAX = int(os.environ.get("TRADE_TARGET_MAX", "3"))
TRADE_HARD_MAX = int(os.environ.get("TRADE_HARD_MAX", "5"))
DIRECTOR_TOP_FOCUS = int(os.environ.get("DIRECTOR_TOP_FOCUS", "5"))
DIRECTOR_TTL_SEC = int(os.environ.get("DIRECTOR_TTL_SEC", "180"))
DIRECTOR_LLM_INTERVAL_SEC = int(os.environ.get("DIRECTOR_LLM_INTERVAL_SEC", "180"))
REPLAY_LOG_PATH = os.environ.get("REPLAY_LOG_PATH", "replay_decisions.jsonl")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", "450"))
OPENROUTER_TIMEOUT_SEC = int(os.environ.get("OPENROUTER_TIMEOUT_SEC", "12"))
OPENROUTER_COOLDOWN_SEC = int(os.environ.get("OPENROUTER_COOLDOWN_SEC", "120"))
OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "")
OPENROUTER_APP_NAME = os.environ.get("OPENROUTER_APP_NAME", "")


# Optional external keys
TRADING_ECON_KEY = os.environ.get("TRADING_ECON_KEY", "")
NEWSAPI_KEY      = os.environ.get("NEWSAPI_KEY", "")

# Optional rates for carry bias
def _rf(code): 
    return float(os.environ.get(f"RF_{code}", "0.0"))
RF = {c: _rf(c) for c in ["USD","EUR","GBP","JPY","AUD","CHF","CAD","NZD"]}

HOST = os.environ.get("OANDA_HOST", "https://api-fxpractice.oanda.com/v3")
WF_STATE_PATH = os.environ.get("WF_STATE_PATH", "walk_forward_state.json")
CALIBRATION_STATE_PATH = os.environ.get("CALIBRATION_STATE_PATH", "research_outputs/calibration.json")
QUANTILE_STATE_PATH = os.environ.get("QUANTILE_STATE_PATH", "research_outputs/quantile_runtime.json")

DEFAULT_SAFE_PROFILE = {
    "min_score": 0.25,
    "min_rr": 1.0,
    "min_pwin": 0.50,
    "time_stop_bars": 6,
}

runtime_state_cache = {"ts": 0.0, "profiles": {}, "quantile": {}, "calibration": {}}

# ======== COMMENTARY CONFIG ========
SUMMARY_EVERY_SEC = int(os.environ.get("SUMMARY_EVERY_SEC", "120"))  # default 2min
COMMENTARY_ENABLED = True  # toggled by "commentary on/off" from the command bar

def llm_rewrite_summary(plain_summary: str) -> str:
    """Optional LLM rewrite. If no OPENAI_API_KEY, just return plain text."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return plain_summary
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Rewrite this trading status into clear, concise English for a non-technical reader. Keep facts, cut jargon."},
                {"role": "user", "content": plain_summary}
            ],
            "temperature": 0.2,
            "max_tokens": 220
        }
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
        r.raise_for_status()
        j = r.json()
        return j["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"[AI] rewrite failed: {e}")
        return plain_summary

def build_plain_summary() -> str:
    """Short snapshot from what your bot already tracks."""
    try:
        acct = get_account_summary()
        nav = float(acct.get("NAV", 0.0)); ccy = acct.get("currency", "USD")
    except Exception:
        nav, ccy = 0.0, "USD"

    try:
        total_pl, win_rate, total_unrl = compute_pl_winrate()
    except Exception:
        total_pl, win_rate, total_unrl = 0.0, 0.0, 0.0

    macro = fetch_macro_context() or {}
    dxy_bias = (macro.get("DXY_proxy") or {}).get("bias", "unavailable")
    events = fetch_econ_calendar() or []
    next_event = events[0] if events else {}
    next_ev_str = f"{next_event.get('when','?')} {next_event.get('currency','')} {next_event.get('event','')}".strip()

    var_est = portfolio_var(price_cache, horizon_days=1, cl=0.99)
    var99 = float(var_est.get("param", 0.0))
    sharpe_est = strategy_sharpe()

    scored = []
    for ins in INSTRUMENTS:
        sig = signal_cache.get(ins, {})
        if isinstance(sig, dict) and "score" in sig:
            scored.append((ins, float(sig["score"]), sig))
    scored.sort(key=lambda x: abs(x[1]), reverse=True)
    top = scored[:3]

    lines = [
        f"Account: NAV {nav:.2f} {ccy} | P/L total {total_pl:.2f} ({total_unrl:+.2f} unrlzd) | Win rate {win_rate:.1f}%",
        f"Macro: USD bias {dxy_bias} | Next event: {next_ev_str}",
        f"Risk: VaR(99%)≈{var99:.4f} (limit {VAR_LIMIT_PCT:.4f}) | Strategy Sharpe≈{sharpe_est:.2f}",
    ]
    if top:
        lines.append("Leaders (conviction score):")
        for ins, sc, sig in top:
            brk = sig.get("breakout", 0.0)
            comp = sig.get("compression", 0.0)
            lux = sig.get("lux_draw", 0.0)
            pwin = sig.get("pwin", 0.0)
            lines.append(f" • {ins}: score {sc:+.2f}, p(win)~{pwin:.2f}, breakout {brk:+.2f}, compression {comp:.2f}, lux {lux:+.2f}")
    return "\n".join(lines)

# ========= LOGGING =========
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logger = logging.getLogger('IntradayBot')

# ========= OANDA SESSION =========
session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {OANDA_API_KEY}",
    "Content-Type": "application/json"
})

# ========= STATE =========
last_trade_ts    = {instr: 0 for instr in INSTRUMENTS}
signal_cache     = {}
price_cache      = {}
spread_cache     = {}
cache_timestamp  = {}
spread_history   = defaultdict(lambda: deque(maxlen=720))  # ~ 1 hour of M5 spreads
instr_meta       = {}
ml_weights       = {}
exp3_weights     = {}
weights_prob     = {}
exp3_gamma       = 0.07
trade_pnl_history = deque(maxlen=2000)
portfolio_positions = {}
signal_dedup_state = {}
executed_signal_ids = {}
strategy_perf = defaultdict(lambda: deque(maxlen=200))
trade_entry_meta = {}
feature_attribution_log = deque(maxlen=5000)
daily_risk_state = {"day": None, "start_nav": None, "peak_nav": None, "kill": False}
latest_plan_cache = {}
recent_plan_ids = {}
strategy_disable_until = {}
strategy_stats = defaultdict(lambda: {"n":0, "wins":0, "sum_r":0.0, "last50": deque(maxlen=50)})
last_tx_seen = None
director_state = {"ts": 0.0, "decision": None, "cache": {}}
openrouter_state = {"last_call": 0.0, "cache": {}}
execution_stats = ExecutionStats(maxlen=200)
edge_monitor = EdgeHealthMonitor()
trade_intel_pipeline = build_default_pipeline(load_trade_intel_config())
portfolio_limits = PortfolioLimits(max_net_ccy_exposure_pct=MAX_NET_CCY_EXPOSURE_PCT, max_gross_ccy_exposure_pct=MAX_GROSS_CCY_EXPOSURE_PCT, daily_risk_pct=DAILY_RISK_PCT, max_cluster_risk_pct=CLUSTER_HEAT_LIMIT)
ops_state = {"session_day": None, "last_session": None, "playbook": {}}
daily_trade_budget = {
    "day": None,
    "trades_opened_today": 0,
    "trades_closed_today": 0,
    "opportunities_seen": defaultdict(int),
    "missed_trades": 0,
    "mode": "normal",
    "last_open_ts": 0.0,
    "consecutive_losses": 0,
}
bandit_state = defaultdict(lambda: defaultdict(lambda: {"alpha": 1.0, "beta": 1.0}))

# Analysis / Ops log
from threading import Lock
analysis_log = deque(maxlen=LOG_MAX)
_log_lock = Lock()


# Enrichment caches
macro_cache = {"ts": 0, "data": {}}
econ_cache  = {"ts": 0, "data": []}
cot_cache   = {"ts": 0, "data": {"status":"unavailable"}}
sent_cache  = {"ts": 0, "data": {}}
corr_cache  = {"ts": 0, "data": {}}
context_blob = {}
orderflow_cache = {}

SESSION_WINDOWS = [
    ("ASIA", 19 * 60, 24 * 60),
    ("ASIA", 0, 2 * 60),
    ("LONDON", 2 * 60, 8 * 60),
    ("OVERLAP", 8 * 60, 11 * 60),
    ("NY", 11 * 60, 17 * 60),
]

SESSION_RULES = {
    "SQUEEZE_BREAKOUT": {"allowed": {"LONDON", "NY", "OVERLAP"}},
    "TREND_PULLBACK": {"allowed": {"LONDON", "NY", "OVERLAP"}},
    "RANGE_MEAN_REVERSION": {"allowed": {"ASIA", "DEAD_ZONE"}},
    "LIQUIDITY_SWEEP_REVERSAL": {"allowed": {"ASIA", "LONDON"}},
}

SESSION_MULTIPLIERS = {
    "ASIA": {"min_ev": 1.05, "min_rr": 1.0, "spread_max_mult": 1.0, "risk_mult": 0.9},
    "LONDON": {"min_ev": 1.0, "min_rr": 1.0, "spread_max_mult": 1.0, "risk_mult": 1.1},
    "NY": {"min_ev": 1.0, "min_rr": 1.0, "spread_max_mult": 1.0, "risk_mult": 1.0},
    "OVERLAP": {"min_ev": 0.95, "min_rr": 0.95, "spread_max_mult": 1.15, "risk_mult": 1.2},
    "DEAD_ZONE": {"min_ev": 1.25, "min_rr": 1.2, "spread_max_mult": 0.8, "risk_mult": 0.6},
}

USD_HEAVY_PAIRS = {"EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD", "USD_CAD", "USD_CHF", "USD_JPY"}

# ========= CACHE HELPERS =========



def current_session_info(now_ny=None):
    now_ny = now_ny or datetime.now(NY_TZ)
    minute = now_ny.hour * 60 + now_ny.minute
    session_name = "DEAD_ZONE"
    end_minute = 24 * 60
    for name, start, end in SESSION_WINDOWS:
        if start <= minute < end:
            session_name = name
            end_minute = end
            break
    minutes_to_change = end_minute - minute if end_minute >= minute else (24 * 60 - minute + end_minute)
    return {
        "session_name": session_name,
        "minutes_to_session_change": int(minutes_to_change),
        "is_liquid_session": session_name in {"LONDON", "NY", "OVERLAP"}
    }


def detect_strategy_profile(sigs, score):
    breakout = abs(float(sigs.get("breakout", 0.0)))
    compression = float(sigs.get("compression", 0.0))
    trend = abs(float(sigs.get("trend", 0.0)))
    meanrev = abs(float(sigs.get("meanrev", 0.0)))
    lux = abs(float(sigs.get("lux_draw", 0.0)))
    if breakout > 0.25 and compression > 0.4:
        return "SQUEEZE_BREAKOUT"
    if lux > 0.45:
        return "LIQUIDITY_SWEEP_REVERSAL"
    if trend >= meanrev and abs(score) > 0.3:
        return "TREND_PULLBACK"
    return "RANGE_MEAN_REVERSION"


def strategy_allowed_in_session(strategy_name, session_name):
    allowed = SESSION_RULES.get(strategy_name, {}).get("allowed", set())
    if not allowed:
        return True
    return session_name in allowed


def session_rule_pack(session_name):
    return SESSION_MULTIPLIERS.get(session_name, SESSION_MULTIPLIERS["NY"])


def _float_any(d, keys, default=0.0):
    for k in keys:
        if k in d:
            try:
                return float(d.get(k, default))
            except Exception:
                continue
    return float(default)


def get_orderflow_features(instr, price, atr_val):
    now = time.time()
    cached = orderflow_cache.get(instr)
    if cached and now - cached["ts"] < ORDERFLOW_TTL:
        return cached["data"]

    features = {
        "available": False,
        "positionbook_available": False,
        "orderbook_available": False,
        "pos_skew_norm": 0.0,
        "crowding_strength": 0.0,
        "nearest_wall_above_px": None,
        "nearest_wall_below_px": None,
        "wall_distance_atr_above": None,
        "wall_distance_atr_below": None,
        "wall_strength_above": 0.0,
        "wall_strength_below": 0.0,
        "sl_wall_risk": 0.0,
        "tp_wall_adjusted": False,
        "tp_wall_cut_distance_atr": 0.0,
    }

    try:
        pb = safe_get(f"{HOST}/instruments/{instr}/positionBook") or {}
        buckets = (pb.get("positionBook") or {}).get("buckets", pb.get("buckets", []))
        longs = [_float_any(b, ["longCountPercent", "longCount"], 0.0) for b in buckets]
        shorts = [_float_any(b, ["shortCountPercent", "shortCount"], 0.0) for b in buckets]
        if longs and shorts:
            raw_skew = (sum(longs) - sum(shorts)) / (sum(longs) + sum(shorts) + 1e-9)
            norm = float(np.tanh(raw_skew * 3.0))
            features["positionbook_available"] = True
            features["pos_skew_norm"] = max(-1.0, min(1.0, norm))
            features["crowding_strength"] = min(1.0, abs(features["pos_skew_norm"]))
    except Exception:
        pass

    try:
        ob = safe_get(f"{HOST}/instruments/{instr}/orderBook") or {}
        buckets = (ob.get("orderBook") or {}).get("buckets", ob.get("buckets", []))
        walls_above = []
        walls_below = []
        strengths = []
        for b in buckets:
            px = _float_any(b, ["price"], 0.0)
            longp = _float_any(b, ["longCountPercent", "longCount"], 0.0)
            shortp = _float_any(b, ["shortCountPercent", "shortCount"], 0.0)
            ordp = _float_any(b, ["orderCountPercent", "orderCount"], longp + shortp)
            strength = max(ordp, longp + shortp)
            if px <= 0 or strength <= 0:
                continue
            strengths.append(strength)
            if px >= price:
                walls_above.append((px, strength))
            else:
                walls_below.append((px, strength))
        if strengths:
            denom = max(np.percentile(strengths, 90), 1e-9)
            walls_above = sorted(walls_above, key=lambda x: abs(x[0] - price))[:5]
            walls_below = sorted(walls_below, key=lambda x: abs(x[0] - price))[:5]
            if walls_above:
                px, st = walls_above[0]
                features["nearest_wall_above_px"] = px
                features["wall_strength_above"] = float(min(2.0, st / denom))
                features["wall_distance_atr_above"] = float(abs(px - price) / max(atr_val, 1e-9))
            if walls_below:
                px, st = walls_below[0]
                features["nearest_wall_below_px"] = px
                features["wall_strength_below"] = float(min(2.0, st / denom))
                features["wall_distance_atr_below"] = float(abs(price - px) / max(atr_val, 1e-9))
            features["orderbook_available"] = True
    except Exception:
        pass

    features["available"] = features["positionbook_available"] or features["orderbook_available"]
    orderflow_cache[instr] = {"ts": now, "data": features}
    return features


def apply_orderflow_confidence_adjustments(direction, confidence, pwin, evr, off):
    notes = []
    if off.get("positionbook_available"):
        skew = off.get("pos_skew_norm", 0.0)
        crowd = off.get("crowding_strength", 0.0)
        crowd_dir = 1 if skew > 0 else -1
        if crowd > 0.2:
            if direction != crowd_dir:
                confidence += 0.05 * crowd
                notes.append("contrarian crowding bonus")
            else:
                confidence -= 0.08 * crowd
                notes.append("with-crowding penalty")
    if off.get("orderbook_available"):
        dist_key = "wall_distance_atr_above" if direction > 0 else "wall_distance_atr_below"
        str_key = "wall_strength_above" if direction > 0 else "wall_strength_below"
        dist = off.get(dist_key)
        wall_s = off.get(str_key, 0.0)
        if dist is not None and dist < 0.6 and wall_s > 0.8:
            penalty = min(0.15, (0.6 - dist) * 0.2 + 0.05 * wall_s)
            confidence -= penalty
            notes.append("near-wall follow-through penalty")
    confidence = float(max(0.05, min(0.95, confidence)))
    pwin = float(max(0.05, min(0.95, pwin + (confidence - 0.5) * 0.1)))
    evr = float(evr * (0.9 + confidence * 0.2))
    return confidence, pwin, evr, notes


def adjust_tp_sl_with_walls(instr, entry, tp, sl, direction, atr_val, off):
    notes = []
    adjusted_tp, adjusted_sl = tp, sl
    if not off.get("orderbook_available"):
        return adjusted_tp, adjusted_sl, off, notes

    wall_px = off.get("nearest_wall_above_px") if direction > 0 else off.get("nearest_wall_below_px")
    wall_strength = off.get("wall_strength_above") if direction > 0 else off.get("wall_strength_below")
    if wall_px is not None and wall_strength > 0.8:
        if direction > 0 and wall_px < tp:
            adjusted_tp = min(tp, wall_px - 0.2 * atr_val)
            off["tp_wall_adjusted"] = True
            off["tp_wall_cut_distance_atr"] = float(abs(tp - adjusted_tp) / max(atr_val, 1e-9))
            notes.append(f"TP cut before wall@{wall_px:.5f} strength={wall_strength:.2f}")
        elif direction < 0 and wall_px > tp:
            adjusted_tp = max(tp, wall_px + 0.2 * atr_val)
            off["tp_wall_adjusted"] = True
            off["tp_wall_cut_distance_atr"] = float(abs(tp - adjusted_tp) / max(atr_val, 1e-9))
            notes.append(f"TP cut before wall@{wall_px:.5f} strength={wall_strength:.2f}")

    sl_wall = off.get("nearest_wall_below_px") if direction > 0 else off.get("nearest_wall_above_px")
    sl_strength = off.get("wall_strength_below") if direction > 0 else off.get("wall_strength_above")
    if sl_wall is not None and sl_strength > 0.9 and abs(sl - sl_wall) <= 0.3 * atr_val:
        adjusted_sl = sl_wall - 0.2 * atr_val if direction > 0 else sl_wall + 0.2 * atr_val
        off["sl_wall_risk"] = min(1.0, sl_strength / 2.0)
        notes.append(f"SL pushed beyond wall@{sl_wall:.5f} strength={sl_strength:.2f}")

    rr = abs(adjusted_tp - entry) / max(abs(entry - adjusted_sl), 1e-9)
    if rr < 1.0:
        return adjusted_tp, adjusted_sl, off, notes + ["RR below 1 after wall adjustment"]
    return _round_price(instr, adjusted_tp), _round_price(instr, adjusted_sl), off, notes


def instrument_annualized_vol(df, window=RISK_PARITY_VOL_WINDOW):
    if df is None or len(df) < 30:
        return 0.15
    rets = np.log(df["c"] / df["c"].shift(1)).dropna().tail(window)
    if len(rets) < 10:
        return 0.15
    vol = float(rets.std(ddof=1) * math.sqrt(12 * 24 * 252))
    return max(0.05, vol)


def compute_currency_exposures():
    expo = defaultdict(float)
    trades = get_open_trades()
    for t in trades:
        try:
            instr = t.get("instrument", "")
            units = float(t.get("currentUnits", 0.0))
            base, quote = pair_currencies(instr)
            expo[base] += units
            expo[quote] -= units
        except Exception:
            continue
    return expo


def portfolio_heat_ratio(nav=None):
    nav = nav or get_nav()[0]
    if nav <= 0:
        return 0.0
    total = 0.0
    for t in get_open_trades():
        try:
            total += abs(float(t.get("initialMarginRequired", 0.0)))
        except Exception:
            continue
    return float(total / nav)


def usd_cluster_direction(instr, direction):
    if instr not in USD_HEAVY_PAIRS:
        return 0
    base, quote = pair_currencies(instr)
    usd_long = (base == "USD" and direction > 0) or (quote == "USD" and direction < 0)
    return 1 if usd_long else -1


def current_usd_cluster_count(target_dir):
    count = 0
    for t in get_open_trades():
        instr = t.get("instrument", "")
        if instr not in USD_HEAVY_PAIRS:
            continue
        units = float(t.get("currentUnits", 0.0))
        if units == 0:
            continue
        dirn = 1 if units > 0 else -1
        if usd_cluster_direction(instr, dirn) == target_dir:
            count += 1
    return count


def apply_exposure_caps(instr, units, nav):
    if units == 0:
        return 0, {"blocked": True, "reason": "zero_units"}
    exposure = compute_currency_exposures()
    base, quote = pair_currencies(instr)
    trial = exposure.copy()
    trial[base] += units
    trial[quote] -= units
    total_abs = sum(abs(v) for v in trial.values()) + 1e-9
    worst_ccy = max(trial.items(), key=lambda kv: abs(kv[1]) / total_abs)
    worst_share = abs(worst_ccy[1]) / total_abs

    usd_share = abs(trial.get("USD", 0.0)) / total_abs
    max_units = abs(units)
    reason = None
    if worst_share > MAX_CCY_RISK_SHARE:
        scale = MAX_CCY_RISK_SHARE / max(worst_share, 1e-9)
        max_units = int(max(0, abs(units) * scale))
        reason = f"currency cap {worst_ccy[0]}={worst_share:.2f}"
    if usd_share > MAX_USD_CLUSTER_SHARE:
        scale = MAX_USD_CLUSTER_SHARE / max(usd_share, 1e-9)
        max_units = int(min(max_units, max(0, abs(units) * scale)))
        reason = (reason + "; " if reason else "") + f"USD cluster share={usd_share:.2f}"

    heat = portfolio_heat_ratio(nav)
    if heat > MAX_TOTAL_HEAT:
        return 0, {"blocked": True, "reason": f"heat cap {heat:.3f}>{MAX_TOTAL_HEAT:.3f}", "exposure": dict(trial)}

    signed_units = int(math.copysign(max_units, units)) if max_units > 0 else 0
    return signed_units, {
        "blocked": signed_units == 0,
        "reason": reason,
        "worst_currency": worst_ccy[0],
        "worst_share": round(worst_share, 3),
        "usd_share": round(usd_share, 3),
        "exposure": {k: round(v, 2) for k, v in trial.items()}
    }

def get_cache(instr):
    now = time.time()
    if instr in cache_timestamp and now - cache_timestamp[instr] < CACHE_TTL:
        return signal_cache[instr], price_cache[instr]
    return None, None

def set_cache(instr, signal, price):
    signal_cache[instr] = signal
    price_cache[instr] = price
    cache_timestamp[instr] = time.time()


def _read_json(path: str):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def refresh_runtime_state(force=False):
    now = time.time()
    if not force and now - runtime_state_cache.get("ts", 0.0) < 30:
        return runtime_state_cache
    runtime_state_cache["profiles"] = _read_json(WF_STATE_PATH)
    runtime_state_cache["quantile"] = _read_json(QUANTILE_STATE_PATH)
    runtime_state_cache["calibration"] = _read_json(CALIBRATION_STATE_PATH)
    runtime_state_cache["ts"] = now
    return runtime_state_cache


def get_strategy_profile(strategy_name="core"):
    st = refresh_runtime_state().get("profiles", {})
    strat = (st.get("strategies") or {}).get(strategy_name, {})
    chosen = strat.get("selected_profile")
    profiles = st.get("profiles") or {}
    return profiles.get(chosen, DEFAULT_SAFE_PROFILE)


def calibrate_pwin(strategy_name: str, raw_pwin: float):
    cal = refresh_runtime_state().get("calibration", {})
    per = (cal.get("strategy") or {}).get(strategy_name, {})
    a = float(per.get("a", 1.0))
    b = float(per.get("b", 0.0))
    z = a * raw_pwin + b
    out = 1.0 / (1.0 + math.exp(-z))
    return float(max(0.001, min(0.999, out)))


def get_quantile_hint(instr: str):
    q = refresh_runtime_state().get("quantile", {})
    by_ins = (q.get("instrument") or {}).get(instr, {})
    return {
        "q10": float(by_ins.get("q10", 0.0)),
        "q50": float(by_ins.get("q50", 0.0)),
        "q90": float(by_ins.get("q90", 0.0)),
    }

# ========= SMALL UTILS =========

def utc_now_iso():
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def pair_currencies(pair):
    base, quote = pair.split("_")
    return base, quote

def session_label(now=None):
    now = now or datetime.now(timezone.utc)
    h = now.hour
    if 0 <= h < 7:
        return "ASIA"
    if 7 <= h < 12:
        return "LONDON"
    if 12 <= h < 17:
        return "OVERLAP"
    if 17 <= h < 21:
        return "NY"
    return "DEAD_ZONE"


def reset_daily_trade_budget_if_needed():
    d = datetime.now(timezone.utc).date().isoformat()
    if daily_trade_budget.get("day") != d:
        daily_trade_budget["day"] = d
        daily_trade_budget["trades_opened_today"] = 0
        daily_trade_budget["trades_closed_today"] = 0
        daily_trade_budget["opportunities_seen"] = defaultdict(int)
        daily_trade_budget["missed_trades"] = 0
        daily_trade_budget["mode"] = "normal"
        daily_trade_budget["consecutive_losses"] = 0


def replay_log(payload):
    try:
        with open(REPLAY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Replay log write failed: {e}")


def clamp01(x):
    return float(np.clip(float(x), 0.0, 1.0))


# ========= ANALYSIS LOG HELPERS =========
def log_event(kind: str, instr: str = None, msg: str = "", data: dict = None, level: int = 1):
    """
    kind: 'SCORE','GUARD','DECISION','RISK','ORDER','INFO'
    level: 1=basic, 2=detailed, 3=trace (filtered by LOG_VERBOSITY)
    """
    if level > LOG_VERBOSITY:
        return
    entry = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "kind": kind,
        "instr": instr,
        "msg": msg,
        "data": data or {}
    }
    try:
        with _log_lock:
            analysis_log.appendleft(entry)
    except Exception:
        pass
    # Also mirror to normal logger (truncated data for safety)
    try:
        preview = "" if not data else f" | data={str(data)[:240]}"
        logger.info(f"[{kind}]{f'[{instr}]' if instr else ''} {msg}{preview}")
    except Exception:
        pass

def get_log(n: int = 50):
    with _log_lock:
        return list(analysis_log)[:n]

# ========= FLASK DASHBOARD =========
app = Flask('')

@app.route('/')
def home():
    import pandas as pd

    # Pull balance & PnL history (cached or computed)
    try:
        balance_data = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/summary")
        equity = float(balance_data["account"]["NAV"])
        bal = float(balance_data["account"]["balance"])
        unreal = float(balance_data["account"]["unrealizedPL"])
        pnl = equity - bal
    except Exception:
        equity = bal = unreal = pnl = 0.0

    # Historical PnL sample (replace with your actual history tracking)
    df = pd.read_csv("pnl_history.csv") if os.path.exists("pnl_history.csv") else pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=10),
        "pnl": np.random.randn(10).cumsum()
    })

    # Render interactive chart + command line
    return f"""
    <html>
    <head>
      <title>Mia Trading Dashboard</title>
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      <style>
        body {{
          background-color: #0e0e10;
          color: #e5e5e5;
          font-family: 'Inter', sans-serif;
          margin: 0; padding: 0;
        }}
        .container {{
          width: 90%;
          margin: auto;
          padding: 20px;
        }}
        h1 {{ color: #fafafa; }}
        canvas {{ background: #18181b; border-radius: 12px; padding: 10px; }}
        #cmdBar {{
          width: 100%;
          background: #1f1f23;
          border: 1px solid #3a3a3d;
          color: #e5e5e5;
          padding: 12px;
          border-radius: 10px;
          font-size: 1em;
          outline: none;
          margin-top: 25px;
        }}
        select {{
          background: #1f1f23;
          border: 1px solid #3a3a3d;
          color: #e5e5e5;
          padding: 6px 12px;
          border-radius: 8px;
          margin-left: 10px;
        }}
      </style>
    </head>
    <body>
      <div class="container">
      <div style="margin-top:20px;">
        <h2>Commentary</h2>
        <div id="commentary" style="white-space:pre-wrap;background:#18181b;border:1px solid #3a3a3d;border-radius:12px;padding:12px;min-height:120px;">
          Loading commentary…
      </div>
  <div style="margin-top:8px;font-size:12px;opacity:0.8">
    Commands: <code>commentary on</code>, <code>commentary off</code>, <code>commentary now</code>, <code>setinterval 120</code>
  </div>
</div>
        <h1>Mia — Forex Quant Bot</h1>
        <p>Equity: {equity:.2f} | Balance: {bal:.2f} | Unrealized PnL: {unreal:.2f}</p>
        <div>
          <label for="timeframe">View PnL:</label>
          <select id="timeframe" onchange="loadChart(this.value)">
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly" selected>Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
        </div>
        <canvas id="pnlChart" height="150"></canvas>
        <input type="text" id="cmdBar" placeholder="Enter command (e.g., !status or !auto on)..." onkeypress="if(event.key==='Enter')sendCmd()" />
      </div>
      <script>
      let summaryTimer = null;
      let refreshSec = {SUMMARY_EVERY_SEC};  // server-side injection optional

      async function loadSummary() {{
        try {{
          const res = await fetch('/summary.json');
          const j = await res.json();
          const box = document.getElementById('commentary');
          if (!j.enabled) {{
            box.textContent = "Commentary is OFF. Type `commentary on` in the command bar.";
            return;
          }}
          box.textContent = j.pretty || j.plain || "(no data)";
        }} catch (e) {{
          const box = document.getElementById('commentary');
          box.textContent = "Unable to load commentary.";
        }}
      }}

      function startSummaryLoop() {{
        if (summaryTimer) clearInterval(summaryTimer);
        loadSummary();
        summaryTimer = setInterval(loadSummary, refreshSec * 1000);
      }}

      window.addEventListener('load', startSummaryLoop);


        const data = {df.to_json(orient="records", date_format="iso")};

        function aggregate(tf) {{
          const grouped = {{}};
          data.forEach(r => {{
            const d = new Date(r.date);
            let key;
            if(tf==='daily') key = d.toISOString().split('T')[0];
            if(tf==='weekly') key = d.getFullYear() + '-W' + Math.ceil(d.getDate()/7);
            if(tf==='monthly') key = d.getFullYear() + '-' + (d.getMonth()+1);
            if(tf==='yearly') key = d.getFullYear();
            grouped[key] = (grouped[key]||0) + r.pnl;
          }});
          return Object.entries(grouped).map(([k,v])=>({{k,v}}));
        }}

        let chart;
        function loadChart(tf='monthly') {{
          const agg = aggregate(tf);
          const ctx = document.getElementById('pnlChart').getContext('2d');
          if(chart) chart.destroy();
          chart = new Chart(ctx, {{
            type: 'line',
            data: {{
              labels: agg.map(x=>x.k),
              datasets: [{{
                label: 'PnL',
                data: agg.map(x=>x.v),
                borderColor: '#4f46e5',
                fill: false,
                tension: 0.25
              }}]
            }},
            options: {{
              scales: {{
                x: {{ ticks: {{ color: '#ccc' }} }},
                y: {{ ticks: {{ color: '#ccc' }} }}
              }}
            }}
          }});
        }}
        loadChart();

        async function sendCmd() {{
          const cmd = document.getElementById('cmdBar').value.trim();
          if(!cmd) return;
          await fetch('/cmd', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{cmd}})}});
          document.getElementById('cmdBar').value='';
        }}
      </script>
    </body>
    </html>
    """
@app.route('/cmd', methods=['POST'])
def run_command():
    global COMMENTARY_ENABLED, SUMMARY_EVERY_SEC
    cmd = (request.json.get('cmd','') or '').strip()
    # Log to file as you already do
    try:
        with open("frontend_cmd.log", "a", encoding="utf-8") as f:
            f.write(cmd.replace("\n", " ") + "\n")
    except Exception:
        pass
    out = "ok"

    # Simple command parsing
    low = cmd.lower()
    if low == "commentary on":
        COMMENTARY_ENABLED = True
        out = "Commentary: ON"
    elif low == "commentary off":
        COMMENTARY_ENABLED = False
        out = "Commentary: OFF"
    elif low.startswith("setinterval "):
        try:
            secs = int(low.split(" ", 1)[1])
            SUMMARY_EVERY_SEC = max(15, min(secs, 3600))
            out = f"Summary interval set to {SUMMARY_EVERY_SEC}s"
        except:
            out = "Usage: setinterval <seconds>"
    elif low == "commentary now":
        # On-demand summary build; you can poll /summary.json from the front-end immediately
        out = "Commentary requested; refreshing…"
    return jsonify({"ok": True, "message": out})


@app.route('/log.json')
def log_json():
    try:
        n = int(request.args.get("n", "200"))
    except Exception:
        n = 200
    return jsonify({"log": get_log(n)})

@app.route('/summary.json')
def summary_json():
    if not COMMENTARY_ENABLED:
        return jsonify({"enabled": False, "plain": "", "pretty": ""})
    plain = build_plain_summary()
    pretty = llm_rewrite_summary(plain)
    decision = director_state.get("decision") or {}
    bandit_view = {s: {k: round(v["alpha"] / (v["alpha"] + v["beta"]), 3) for k, v in arms.items()} for s, arms in bandit_state.items()}
    return jsonify({
        "enabled": True,
        "plain": plain,
        "pretty": pretty,
        "director_selected": decision.get("focus", []),
        "trade_budget": {
            "target": [TRADE_TARGET_MIN, TRADE_TARGET_MAX],
            "actual": daily_trade_budget.get("trades_opened_today", 0),
            "max": TRADE_HARD_MAX,
            "mode": daily_trade_budget.get("mode", "normal"),
        },
        "bandit_weights": bandit_view,
        "top_opportunity": sorted([(i, (signal_cache.get(i, {}) or {}).get("opportunity_score", 0.0)) for i in INSTRUMENTS], key=lambda x: x[1], reverse=True)[:5],
    })


def run_flask():
    port = int(os.environ.get("PORT", "5000"))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========= OANDA HELPERS =========

def safe_get(url, params=None, retries=3):
    for _ in range(retries):
        try:
            r = session.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"API call failed: {e}")
            time.sleep(1)
    return None

def safe_post(url, json_data=None, retries=3):
    for _ in range(retries):
        try:
            r = session.post(url, json=json_data, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"API POST failed: {e}")
            time.sleep(1)
    return None

def get_account_summary():
    data = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/summary")
    if data: 
        return data["account"]
    return {"NAV":0, "currency":"USD"}

def get_open_trades(instr=None):
    data = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/openTrades")
    trades = data.get("trades",[]) if data else []
    if instr: 
        trades = [t for t in trades if t["instrument"]==instr]
    return trades

def get_positions_info():
    info=[]
    for instr in INSTRUMENTS:
        for t in get_open_trades(instr):
            info.append({
                "instrument": instr,
                "units": t["currentUnits"],
                "unrealized_pl": float(t.get("unrealizedPL",0))
            })
            try:
                portfolio_positions[instr] = int(portfolio_positions.get(instr, 0)) + int(t["currentUnits"])
            except Exception:
                pass
    return info

def compute_pl_winrate():
    # Fetch closed order fills
    resp = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/transactions")
    closed = resp.get("transactions", []) if resp else []
    closed = [t for t in closed if t.get("type") == "ORDER_FILL"]

    # Compute realized PnL and trade stats
    realized_pnls = [float(t.get("pl", "0")) for t in closed if float(t.get("pl", "0")) != 0]
    total_realized = sum(realized_pnls)
    total_trades = len(realized_pnls)
    winning = sum(1 for p in realized_pnls if p > 0)
    winrate = (winning / total_trades * 100) if total_trades > 0 else 0.0

    # Compute unrealized PnL from open trades
    total_unrealized = 0.0
    for instr in INSTRUMENTS:
        open_trades = get_open_trades(instr)
        for t in open_trades:
            total_unrealized += float(t.get("unrealizedPL", 0.0))

    total_pl = total_realized + total_unrealized
    return total_pl, winrate, total_unrealized

def record_pnl_snapshot(path="pnl_history.csv"):
    try:
        total_pl, win_rate, total_unrealized = compute_pl_winrate()
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        row = f"{now},{total_pl}\n"
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write("date,pnl\n")
        with open(path, "a") as f:
            f.write(row)
    except Exception:
        pass

def manage_active_trades(instr, sl_buffer=0.04):
    """State-driven lifecycle manager: +1R BE, +1.5R partial, ATR trail, time-stop, invalidation exit."""
    trades = get_open_trades(instr)
    if not trades:
        return

    latest_sig = signal_cache.get(instr, {}) if isinstance(signal_cache.get(instr), dict) else {}
    flip_score = float(latest_sig.get("score", 0.0) or 0.0)
    votes, _ = mtf_direction_vote(instr)
    h1_vote = votes.get("H1", 0)

    for t in trades:
        tid = t.get("id")
        ep = float(t.get("price", 0.0) or 0.0)
        sl = float((t.get("stopLossOrder") or {}).get("price", ep))
        side = int(float(t.get("currentUnits", 0) or 0))
        units_abs = abs(side)
        mid = float(get_midprice(instr) or ep)
        if side == 0 or units_abs == 0:
            continue

        risk_per_unit = max(abs(ep - sl), 1e-9)
        r_mult = ((mid - ep) / risk_per_unit) if side > 0 else ((ep - mid) / risk_per_unit)

        meta = trade_entry_meta.setdefault(tid, {"ts": time.time(), "be_moved": False, "partial_taken": False, "time_stop_bars": TIME_STOP_BARS})
        bars_open = (time.time() - meta["ts"]) / max(COOLDOWN_SEC, 1)
        time_stop_bars = int(meta.get("time_stop_bars", TIME_STOP_BARS) or TIME_STOP_BARS)

        intel_tid = meta.get("trade_intel_id")
        if intel_tid:
            ti_update = trade_intel_pipeline.on_trade_update(
                {
                    "trade_id": intel_tid,
                    "r_multiple": float(r_mult),
                    "seconds_held": int(time.time() - meta.get("ts", time.time())),
                    "structure_confirmed": bool(abs(flip_score) < 0.75),
                },
                {
                    "execution_risk_score": float(np.clip((spread_cache.get(instr, 0.0) or 0.0) * 10000.0 / 5.0, 0.0, 1.0)),
                    "regime_alignment_score": 0.1 if ((side > 0 and h1_vote < 0) or (side < 0 and h1_vote > 0)) else 0.8 if abs(h1_vote) > 0 else 0.5,
                    "near_profile_level": bool(abs(r_mult) > 1.0),
                },
            )
            action = ((ti_update or {}).get("instruction") or {}).get("action")
            if action == "take_partial" and (not meta.get("partial_taken")):
                cut_units = -int(math.copysign(max(1, int(units_abs * PARTIAL_CLOSE_FRACTION)), side))
                place_market_order(instr, cut_units)
                meta["partial_taken"] = True
                trade_intel_pipeline.on_trade_partial({"trade_id": intel_tid}, {"cut_units": cut_units}, {"instrument": instr})
            elif action == "arm_break_even" and (not meta.get("be_moved")) and t.get("stopLossOrder", {}).get("id"):
                new_sl = ep + sl_buffer * risk_per_unit if side > 0 else ep - sl_buffer * risk_per_unit
                safe_put(
                    f"{HOST}/accounts/{OANDA_ACCOUNTID}/orders/{t['stopLossOrder']['id']}",
                    json_data={"order": {"price": f"{_round_price(instr, new_sl)}"}},
                )
                meta["be_moved"] = True
            elif action == "force_exit":
                place_market_order(instr, -side)
                log_event("MANAGE", instr, f"{tid}: trade-intel force exit", {"r": r_mult}, level=1)
                continue

        if (not meta["be_moved"]) and r_mult >= 1.0 and t.get("stopLossOrder", {}).get("id"):
            new_sl = ep + sl_buffer * risk_per_unit if side > 0 else ep - sl_buffer * risk_per_unit
            safe_put(
                f"{HOST}/accounts/{OANDA_ACCOUNTID}/orders/{t['stopLossOrder']['id']}",
                json_data={"order": {"price": f"{_round_price(instr, new_sl)}"}},
            )
            meta["be_moved"] = True
            log_event("MANAGE", instr, f"{tid}: SL -> BE+buffer at +1R", {"new_sl": new_sl}, level=1)

        if (not meta["partial_taken"]) and r_mult >= 1.5:
            cut_units = -int(math.copysign(max(1, int(units_abs * PARTIAL_CLOSE_FRACTION)), side))
            place_market_order(instr, cut_units)
            meta["partial_taken"] = True
            log_event("MANAGE", instr, f"{tid}: partial take at +1.5R", {"cut_units": cut_units}, level=1)

        # trailing after partial: ATR based
        if meta.get("partial_taken") and t.get("stopLossOrder", {}).get("id"):
            df = get_candles(instr, count=120, granularity="M5")
            if df is not None and len(df) > 30:
                atrv = float(atr(df, ATR_PERIOD).iloc[-1] or 0.0)
                trail_sl = mid - 1.2 * atrv if side > 0 else mid + 1.2 * atrv
                if (side > 0 and trail_sl > sl) or (side < 0 and trail_sl < sl):
                    safe_put(
                        f"{HOST}/accounts/{OANDA_ACCOUNTID}/orders/{t['stopLossOrder']['id']}",
                        json_data={"order": {"price": f"{_round_price(instr, trail_sl)}"}},
                    )
                    log_event("MANAGE", instr, f"{tid}: ATR trail", {"trail_sl": trail_sl}, level=2)

        if bars_open >= time_stop_bars and r_mult < TIME_STOP_PROGRESS_R:
            place_market_order(instr, -side)
            log_event("MANAGE", instr, f"{tid}: time-stop exit", {"bars_open": bars_open, "r": r_mult}, level=1)
            continue

        invalidation = (side > 0 and h1_vote < 0) or (side < 0 and h1_vote > 0)
        if invalidation or (side > 0 and flip_score <= -0.5) or (side < 0 and flip_score >= 0.5):
            place_market_order(instr, -side)
            log_event("MANAGE", instr, f"{tid}: invalidation/opposite exit", {"score": flip_score, "h1": h1_vote}, level=1)


def safe_put(url, json_data=None, retries=3):
    for _ in range(retries):
        try:
            r = session.put(url, json=json_data, timeout=30)
            r.raise_for_status()
            return r.json() if r.text else {}
        except Exception as e:
            logger.warning(f"API PUT failed: {e}")
            time.sleep(1)
    return None


# --- Timezone (NY) ---
from datetime import datetime, timezone, timedelta
from pathlib import Path
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
    NY_TZ = ZoneInfo("America/New_York")
except Exception:
    # Fallback (no DST). If you can, prefer ZoneInfo above.
    NY_TZ = timezone(timedelta(hours=-4))

CLOSEOUT_HOUR = 17  # 5 PM New York
_last_closeout_date = None  # guard so we only close once per day

# --- Close helpers ---
def close_all(instr: str):
    """Flatten instrument by sending a market order for the negative of current net units."""
    u = net_units(instr)
    if u != 0:
        place_market_order(instr, -u)

def closeout_all_positions():
    """Flatten the entire book (all instruments)."""
    any_closed = False
    for ins in INSTRUMENTS:
        if get_open_trades(ins):
            close_all(ins)
            any_closed = True
            log_event("CLOSEOUT", ins, "Closed at session end (17:00 NY)", level=1)
    if any_closed:
        logger.info("[SESSION] All positions closed at 17:00 NY")



# ========= INSTRUMENT META / PRICING (poll) =========

def get_instruments_meta():
    data = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/instruments")
    if not data: 
        return
    for ins in data.get("instruments", []):
        instr_meta[ins["name"]] = {
            "pipLocation": ins.get("pipLocation", -4),
            "displayPrecision": ins.get("displayPrecision", 5)
        }

def get_midprice(instr):
    mid = price_cache.get(instr)
    if mid is None:
        refresh_pricing_once()
        mid = price_cache.get(instr)
    return mid


def _round_price(instr, px):
    prec = instr_meta.get(instr, {}).get("displayPrecision", 5)
    try: 
        return float(f"{px:.{prec}f}")
    except Exception: 
        return float(px)

def refresh_pricing_once():
    try:
        params = {"instruments": ",".join(INSTRUMENTS)}
        data = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/pricing", params=params) or {}
        for p in data.get("prices", []):
            instr = p["instrument"]
            bids = p.get("bids",[]); asks = p.get("asks",[])
            if not bids or not asks: 
                continue
            bid = float(bids[0]["price"]); ask = float(asks[0]["price"])
            mid = (bid+ask)/2.0; spr = max(ask-bid, 0.0)
            price_cache[instr] = mid
            spread_cache[instr] = spr
            spread_history[instr].append((time.time(), spr))
    except Exception:
        pass

# ========= MARKET DATA =========

def get_candles(instr, count=500, granularity=GRANULARITY):
    params = {"price":"M","granularity":granularity,"count":count}
    data = safe_get(f"{HOST}/instruments/{instr}/candles", params=params)
    if not data or "candles" not in data: 
        return None
    rows=[]
    for c in data["candles"]:
        if not c.get("complete"): 
            continue
        mid = c["mid"]
        rows.append({
            "time": c["time"],
            "o": float(mid["o"]),
            "h": float(mid["h"]),
            "l": float(mid["l"]),
            "c": float(mid["c"]),
            "v": int(c.get("volume", 0))  # <-- add this line
        })
    df = pd.DataFrame(rows)
    return df if len(df)>0 else None


# ========= INDICATORS =========

def ema(series, n): 
    return series.ewm(span=n, adjust=False).mean()

def true_range(df):
    prev_close = df["c"].shift(1)
    tr = pd.concat([(df["h"]-df["l"]).abs(),
                    (df["h"]-prev_close).abs(),
                    (df["l"]-prev_close).abs()], axis=1).max(axis=1)
    return tr

def atr(df, n=14): 
    return true_range(df).rolling(n).mean()

def zscore(series, lookback=200):
    s = series.tail(lookback)
    mu, sigma = s.mean(), s.std(ddof=0)
    sigma = sigma if sigma>1e-12 else 1e-6
    return (series - mu)/sigma

def jarque_bera(logret):
    x = logret.dropna()
    if len(x) < 24: 
        return 0.0, 1.0
    n = len(x)
    s = statistics.pstdev(x)
    if s == 0: 
        return 0.0, 1.0
    skew = (np.mean(((x - np.mean(x))/s)**3))
    kurt = (np.mean(((x - np.mean(x))/s)**4))
    jb = n/6.0*(skew**2 + (kurt-3.0)**2/4.0)
    p = math.exp(-0.5*jb) if jb<30 else 0.0
    return jb, p

def gbm_mle_mu_sigma(prices):
    px = pd.Series(prices).dropna()
    if len(px)<30: 
        return 0.0, 0.0
    r = np.log(px/px.shift(1)).dropna()
    mu = r.mean() * (12*24*252)
    sigma = r.std(ddof=1) * math.sqrt(12*24*252)
    return float(mu), float(sigma)

def kalman_level(price, R=0.01, Q=0.001):
    x, P = price.iloc[0], 1.0
    xs=[]
    for z in price:
        x_pred, P_pred = x, P + Q
        K = P_pred/(P_pred + R)
        x = x_pred + K*(z - x_pred)
        P = (1 - K)*P_pred
        xs.append(x)
    return pd.Series(xs, index=price.index)

# ========= SIGNALS / ML / ENSEMBLE =========

def position_book_skew(pb):
    try:
        buckets = pb["positionBook"]["buckets"]
    except Exception:
        buckets = pb.get("buckets", [])
    if not buckets: 
        return 0.0
    longs = [float(b.get("longCountPercent",0)) for b in buckets if "longCountPercent" in b]
    shorts= [float(b.get("shortCountPercent",0)) for b in buckets if "shortCountPercent" in b]
    if not longs or not shorts: 
        return 0.0
    longp = sum(longs)/len(longs); shortp = sum(shorts)/len(shorts)
    return (longp - shortp)/100.0

def fetch_positionbook(instr):
    return safe_get(f"{HOST}/instruments/{instr}/positionBook") or {}

def build_signals(df, instr):
    s = {}
    price = df["c"].iloc[-1]
    ema_mid = ema(df["c"], EMA_PERIOD)
    mr_z = zscore(df["c"] - ema_mid, lookback=min(ZS_LOOKBACK, len(df)))
    s["meanrev"] = float((-mr_z.iloc[-1]).clip(-3,3)/3.0)

    ema_f, ema_s = ema(df["c"], EMA_FAST), ema(df["c"], EMA_SLOW)
    slope = ema_f.diff().rolling(5).mean()
    mom = np.tanh((ema_f - ema_s) / (df["c"].rolling(50).std(ddof=0) + 1e-9))
    slope_norm = np.tanh((slope / (df["c"].rolling(50).std(ddof=0) + 1e-9)).fillna(0))
    s["trend"] = float(((mom + slope_norm)/2.0).fillna(0).iloc[-1])

    klevel = kalman_level(df["c"].fillna(method="ffill"))
    kdev = (df["c"] - klevel)
    k_z = zscore(kdev, lookback=min(ZS_LOOKBACK, len(df)))
    s["kalman"] = float((-k_z.iloc[-1]).clip(-3,3)/3.0)

    pb = fetch_positionbook(instr)
    s["pos_skew"] = float(position_book_skew(pb) if pb else 0.0)

    logret = np.log(df["c"]/df["c"].shift(1))
    jb, p = jarque_bera(logret.tail(JB_LOOKBACK))
    s["fat_tails"] = float(np.tanh(max(0.0, jb)/10.0))

    mu_gbm, sigma_gbm = gbm_mle_mu_sigma(df["c"])
    s["gbm_sigma"] = float(np.tanh(sigma_gbm))
    return s, {"jb": jb, "jb_p": p, "mu_gbm": mu_gbm, "sigma_gbm": sigma_gbm}

def ml_features(df, sigs, diag):
    price = df["c"].iloc[-1]
    atrv = atr(df, ATR_PERIOD).iloc[-1] / (price + 1e-9)
    mom = sigs.get("trend",0)
    mr  = sigs.get("meanrev",0)
    kal = sigs.get("kalman",0)
    skew= sigs.get("pos_skew",0)
    tails=sigs.get("fat_tails",0)
    sig  = diag.get("sigma_gbm",0)
    return np.array([1.0, mom, mr, kal, skew, tails, atrv, sig], dtype=float)

def ml_predict_proba(instr, x):
    w = ml_weights.get(instr)
    if w is None:
        w = np.zeros(x.shape[0], dtype=float)
        ml_weights[instr] = w
    z = float(w @ x)
    p = 1.0/(1.0 + math.exp(-z))
    return p

def ml_update(instr, x, y, lr=0.05, lam=0.001):
    w = ml_weights.get(instr, np.zeros(x.shape[0], dtype=float))
    z = float(w @ x)
    p = 1.0/(1.0 + math.exp(-z))
    grad = (p - y)*x + lam*w
    w = w - lr*grad
    ml_weights[instr] = w

def kmeans_1d(feats, k=3, iters=15):
    x = np.array(feats, dtype=float).reshape(-1,1)
    if len(x)<k: 
        return [0]*len(x), [float(np.mean(x)) if len(x)>0 else 0.0]*k
    centers = np.linspace(x.min(), x.max(), k).reshape(-1,1)
    for _ in range(iters):
        d = ((x - centers.T)**2).argmin(axis=1)
        for j in range(k):
            pts = x[d==j]
            if len(pts)>0: 
                centers[j] = pts.mean()
    d = ((x - centers.T)**2).argmin(axis=1)
    return d.tolist(), centers.flatten().tolist()

def regime_from_kmeans(df):
    vols = np.log(df["c"]/df["c"].shift(1)).rolling(40).std().dropna()
    if len(vols)<=10: 
        return "neutral"
    labels, centers = kmeans_1d(vols.values[-90:], k=3)
    reg_id = labels[-1]; ordering = np.argsort(centers)
    if reg_id == ordering[0]: 
        return "range"
    if reg_id == ordering[2]: 
        return "trend"
    return "neutral"

def exp3_choose(instr, arms):
    W = exp3_weights.setdefault(instr, {a:1.0 for a in arms})
    total = sum(W.values())
    probs = {a: (1-exp3_gamma)*(W[a]/total) + exp3_gamma/len(arms) for a in arms}
    weights_prob[instr] = probs
    return probs

def exp3_update(instr, rewards):
    if instr not in exp3_weights: 
        return
    W = exp3_weights[instr]; P = weights_prob.get(instr, {})
    for a, r in rewards.items():
        p = max(P.get(a, 1e-6), 1e-6)
        est = r/p
        W[a] *= math.exp(exp3_gamma*est/len(W))

def carry_signal(instr: str) -> float:
    """Interest-rate differential proxy mapped to [-1, 1]."""
    try:
        base, quote = instr.split("_")
    except ValueError:
        return 0.0
    rd = float(RF.get(base, 0.0)) - float(RF.get(quote, 0.0))
    return float(np.tanh(rd * 20.0))

def value_signal(instr: str, df: pd.DataFrame) -> float:
    """Simple PPP-style value concept: distance from 200-bar fair value."""
    if df is None or len(df) < 220:
        return 0.0
    fair = float(df["c"].rolling(200).mean().iloc[-1])
    atrv = float(atr(df, ATR_PERIOD).iloc[-1])
    if not np.isfinite(fair) or not np.isfinite(atrv) or atrv <= 0:
        return 0.0
    mispricing = (fair - float(df["c"].iloc[-1])) / atrv
    return float(np.tanh(mispricing / 2.0))

def macro_dollar_signal(instr: str) -> float:
    """Directional USD regime tilt from DXY proxy."""
    macro = fetch_macro_context() or {}
    bias = (macro.get("DXY_proxy") or {}).get("bias", "unavailable")
    if bias == "strong":
        dxy_score = 1.0
    elif bias == "moderate":
        dxy_score = 0.35
    elif bias == "weak":
        dxy_score = -0.7
    else:
        return 0.0
    if "USD" not in instr:
        return 0.0
    return float(-dxy_score if instr.startswith("USD_") else dxy_score)

def ensemble_score(instr, df, sigs, diag):
    """
    Enhanced ensemble:
      - Base: trend/meanrev/kalman/pos_skew
      - Online-ML probability
      - Fibonacci confluence (from fib_signals)
      - Liquidity factor (tight spreads, fresh ticks)
      - Higher timeframe alignment (H1/H4/D1 EMA 12/26)
      - Carry/value/macro overlays
    Returns: score ∈ [-1..1], regime, weights, pwin
    """
    # EXP3 arm mix (add 'fib' arm)
    arms = ["trend", "meanrev", "kalman", "pos_skew", "fib"]
    probs = exp3_choose(instr, arms)
    weights = {k: probs.get(k, 1.0 / len(arms)) for k in arms}

    # Regime (range/trend/neutral)
    regime = regime_from_kmeans(df)

    # ML component
    x = ml_features(df, sigs, diag)
    pwin = ml_predict_proba(instr, x)
    ml_signal = 2.0 * pwin - 1.0  # map [0..1] → [-1..1]

    # Fibonacci confluence + bias
    f = fib_signals(df)
    fib_conf = float(f.get("fib_confluence", 0.0))          # 0..1
    fib_sig  = float(f.get("fib_retrace_bias", 0.0) * 0.6 + f.get("fib_ext_bias", 0.0) * 0.4)

    # Liquidity & HTF
    liq = liquidity_factor(instr)                            # 0..1
    htf = higher_tf_alignment(instr)                         # -1..+1

    # Additional finance concepts
    carry_sig = carry_signal(instr)                          # -1..+1
    value_sig = value_signal(instr, df)                      # -1..+1
    macro_sig = macro_dollar_signal(instr)                   # -1..+1

    # Base blend
    base = (
        weights["trend"]   * float(sigs.get("trend", 0.0)) +
        weights["meanrev"] * float(sigs.get("meanrev", 0.0)) +
        weights["kalman"]  * float(sigs.get("kalman", 0.0)) +
        0.15               * float(sigs.get("pos_skew", 0.0)) +
        0.35               * float(ml_signal) +
        0.20               * float(sigs.get("lux_draw", 0.0)) +
        weights["fib"]     * float(fib_sig) * float(fib_conf) +
        0.12               * float(carry_sig) +
        0.10               * float(value_sig) +
        0.08               * float(macro_sig)
    )



    # Regime tilt
    if regime == "range":
        base = 0.6 * base + 0.4 * float(sigs.get("meanrev", 0.0))
    elif regime == "trend":
        base = 0.6 * base + 0.4 * float(sigs.get("trend", 0.0))

    # Liquidity & HTF modulation
    score = base
    score = score * (0.7 + 0.3 * liq)   # 0.7..1.0 depending on liquidity
    score = score + 0.15 * htf          # directional nudge from HTF

    # squash to [-1..1]
    score = float(np.tanh(score))

    # expose diagnostics
    sigs["fib_confluence"] = round(fib_conf, 3)
    sigs["fib_signal"]     = round(fib_sig, 3)
    sigs["liquidity"]      = round(liq, 3)
    sigs["htf_align"]      = round(htf, 3)
    sigs["carry"]          = round(carry_sig, 3)
    sigs["value"]          = round(value_sig, 3)
    sigs["macro_usd"]      = round(macro_sig, 3)

    return float(score), regime, weights, float(pwin)


# ========= MACRO / CALENDAR / POSITIONING / COT / SENTIMENT =========

def fetch_macro_context():
    now = time.time()
    if now - macro_cache["ts"] < MACRO_TTL:
        return macro_cache["data"]
    def px(instr):
        if instr in price_cache and price_cache[instr]>0: 
            return price_cache[instr]
        df = get_candles(instr, count=12)
        return float(df["c"].iloc[-1]) if df is not None and len(df)>0 else np.nan
    try:
        eurusd = px("EUR_USD"); usdjpy = px("USD_JPY"); gbpusd = px("GBP_USD"); usdcad = px("USD_CAD"); usdchf = px("USD_CHF")
        base = 50.14348112
        dxy = base * (eurusd**(-0.576)) * (usdjpy**(0.136)) * (gbpusd**(-0.119)) * (usdcad**(0.091)) * (usdchf**(0.036))
        dxy_bias = "strong" if dxy>105 else "moderate" if dxy>100 else "weak"
    except Exception:
        dxy = None; dxy_bias = "unavailable"
    macro = {
        "DXY_proxy": {"last": dxy, "bias": dxy_bias},
        "XAUUSD": {"last": px("XAU_USD") if "XAU_USD" in INSTRUMENTS else None},
        "WTI": {"last": None, "status": "unavailable"},
        "VIX": {"last": None, "status": "unavailable"},
        "SPX": {"last": None, "status": "unavailable"}
    }
    macro_cache["ts"] = now; macro_cache["data"] = macro
    return macro

def fetch_econ_calendar():
    now = time.time()
    if now - econ_cache["ts"] < ECON_TTL:
        return econ_cache["data"]
    events = []
    try:
        if TRADING_ECON_KEY:
            params = {"c": TRADING_ECON_KEY, "d1": datetime.utcnow().strftime("%Y-%m-%d")}
            data = requests.get("https://api.tradingeconomics.com/calendar", params=params, timeout=20)
            if data.ok:
                j = data.json()
                for e in j:
                    imp = str(e.get("Importance","") or e.get("ImportanceId",""))
                    if imp.lower() in ("3","high","3.0"):
                        when = e.get("DateUTC") or e.get("Date") or ""
                        events.append({
                            "when": when, "currency": e.get("Country",""), "event": e.get("Category",""),
                            "previous": e.get("Previous",""), "consensus": e.get("Forecast",""), "importance":"high"
                        })
        if not events:
            events = [{"when":"unavailable","currency":"","event":"calendar unavailable","previous":"","consensus":"","importance":"-"}]
    except Exception:
        events = [{"when":"unavailable","currency":"","event":"calendar unavailable","previous":"","consensus":"","importance":"-"}]
    econ_cache["ts"] = now; econ_cache["data"] = events[:10]
    return econ_cache["data"]

def fetch_positioning(instr):
    pb = safe_get(f"{HOST}/instruments/{instr}/positionBook") or {}
    ob = safe_get(f"{HOST}/instruments/{instr}/orderBook") or {}
    skew = 0.0; tops=[]
    try:
        buckets = (pb.get("positionBook") or {}).get("buckets", [])
        longs = [float(b.get("longCountPercent",0)) for b in buckets if "longCountPercent" in b]
        shorts= [float(b.get("shortCountPercent",0)) for b in buckets if "shortCountPercent" in b]
        if longs and shorts:
            skew = (sum(longs)/len(longs) - sum(shorts)/len(shorts))/100.0
    except Exception:
        pass
    try:
        ob_b = (ob.get("orderBook") or {}).get("buckets", [])
        mid = price_cache.get(instr, np.nan)
        def level_score(b):
            p = float(b.get("price", 0))
            return -abs(p - (mid if mid==mid else p))
        tops = sorted(ob_b, key=level_score)[:3]
        tops = [{"price": float(b.get("price",0))} for b in tops]
    except Exception:
        tops = []
    contrarian = "fade_longs" if skew>0.15 else "fade_shorts" if skew<-0.15 else "neutral"
    return {"skew": skew, "top_levels": tops, "contrarian": contrarian}

def fetch_COT():
    now = time.time()
    if now - cot_cache["ts"] < COT_TTL:
        return cot_cache["data"]
    try:
        cot = {"status":"unavailable"}
    except Exception:
        cot = {"status":"unavailable"}
    cot_cache["ts"] = now; cot_cache["data"] = cot
    return cot

def fetch_trends_sentiment():
    now = time.time()
    if now - sent_cache["ts"] < ECON_TTL:
        return sent_cache["data"]
    data = {"trends":"unavailable","headlines":"unavailable"}
    try:
        if NEWSAPI_KEY:
            params = {"apiKey": NEWSAPI_KEY, "q": "forex OR dollar OR euro OR yen OR pound OR aussie", "language":"en", "pageSize": 5, "sortBy":"publishedAt"}
            res = session.get("https://newsapi.org/v2/everything", params=params, timeout=10)
            if res.ok:
                j = res.json()
                titles = [a.get("title","") for a in j.get("articles",[])]
                snippet = ("; ".join(titles))[:200]
                data["headlines"] = snippet
    except Exception:
        pass
    sent_cache["ts"] = now; sent_cache["data"] = data
    return data

def correlation_matrix(window=CORR_WIN):
    px = {}
    for ins in ["EUR_USD","GBP_USD","USD_JPY","AUD_USD","USD_CHF","USD_CAD","NZD_USD"]:
        df = get_candles(ins, count=max(120, window+5))
        if df is None: 
            continue
        px[ins] = np.log(df["c"]/df["c"].shift(1)).dropna().tail(window)
    if len(px) < 3:
        return {"status":"unavailable"}
    dfret = pd.DataFrame(px).dropna()
    corr = dfret.corr()
    tri = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i+1, len(cols)):
            a, b = cols[i], cols[j]
            tri.append((a,b,float(corr.loc[a,b])))
    tri.sort(key=lambda x: x[2])
    bottom = tri[:2]
    top = tri[-2:]
    return {"top":[{"pair":f"{a}-{b}","corr":float(c)} for a,b,c in top],
            "bottom":[{"pair":f"{a}-{b}","corr":float(c)} for a,b,c in bottom]}

def compute_beta_alpha(instr):
    dfs = {}
    for ins in INSTRUMENTS:
        df = get_candles(ins, count=300)
        if df is None: 
            return {"status":"unavailable"}
        dfs[ins] = np.log(df["c"]/df["c"].shift(1)).dropna()
    r_i = dfs[instr].dropna()
    mkt = pd.concat([dfs[k] for k in INSTRUMENTS if k!=instr], axis=1).mean(axis=1).loc[r_i.index]
    if len(r_i)<50: 
        return {"status":"unavailable"}
    X = np.vstack([np.ones(len(mkt)), mkt.values]).T
    y = r_i.values
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    beta = float(coef[1]); alpha = float(coef[0]) * (12*24*252)
    yhat = X @ coef
    ss_res = float(np.sum((y - yhat)**2)); ss_tot = float(np.sum((y - y.mean())**2))
    r2 = 0.0 if ss_tot==0 else 1.0 - ss_res/ss_tot
    return {"beta": beta, "alpha_ann": alpha, "r2": r2}

def compute_intraday_regime(df):
    if df is None or len(df)<60:
        return "neutral", 1.0
    price = df["c"]
    logret = np.log(price/price.shift(1)).dropna()
    rv = float(logret.rolling(30).std(ddof=1).iloc[-1])
    atrp = float((df["h"]-df["l"]).rolling(14).mean().iloc[-1]/(price.iloc[-1]+1e-9))
    var1 = logret.var(ddof=1)
    var2 = (logret.rolling(2).sum()).var(ddof=1)
    hurst_proxy = 0.5 if (var1==0 or var2==0) else 0.5*np.log(var2/var1)/np.log(2)
    if rv < 0.0004 and atrp < 0.0010:
        regime = "low_vol"; mult = 0.8
    elif rv > 0.0012 or atrp > 0.0030:
        regime = "high_vol"; mult = 0.9
    else:
        regime = "trending" if hurst_proxy>0.55 else "mean_reverting" if hurst_proxy<0.45 else "neutral"
        mult = 1.2 if regime=="trending" else 1.0 if regime=="neutral" else 1.1
    return regime, float(max(0.5, min(1.5, mult)))

def realized_vol_target(units, df):
    if df is None or len(df)<60 or units==0:
        return units
    logret = np.log(df["c"]/df["c"].shift(1)).dropna()
    instr_ann_vol = float(logret.std(ddof=1) * math.sqrt(12*24*252))
    if instr_ann_vol<=0: 
        return units
    nudge = float(TARGET_ANNUAL_VOL / instr_ann_vol)
    nudge = max(0.7, min(1.3, nudge))
    return int(units * nudge)

def fx_forward_drift(instr):
    base, quote = pair_currencies(instr)
    rd = RF.get(quote, 0.0)  # domestic (quote)
    rf = RF.get(base, 0.0)   # foreign (base)
    mu_rn = rd - rf
    return mu_rn, rd, rf

def event_guardrails(instr):
    """Enhanced event guardrails with Forex Factory + TradingEconomics awareness."""
    # Trading Economics check
    evs = fetch_econ_calendar() or []
    base, quote = instr.split("_")
    now = datetime.utcnow().replace(tzinfo=timezone.utc)

    for e in evs:
        cur = (e.get("currency", "") or "").upper()
        if base in cur or quote in cur or cur in (base, quote):
            when = e.get("when", "")
            try:
                t = datetime.fromisoformat(when.replace("Z", "+00:00"))
            except Exception:
                continue
            if abs((t - now).total_seconds()) <= EVENT_WINDOW_MIN * 60:
                return True

    # Forex Factory news awareness
    avoid_trading, news_events = get_news_awareness(instr)
    if avoid_trading:
        logger.info(f"[{instr}] Blocked by Forex Factory high-impact news: {[e['title'] for e in news_events]}")
        return True

    return False

def fetch_forex_factory_events():
    """
    Fetch high-impact news events from Forex Factory RSS feed
    Returns list of events for next 24 hours
    """
    try:
        url = "https://www.forexfactory.com/ffcal_week_this.xml"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        events = []
        now = datetime.now(timezone.utc)
        next_24h = now + timedelta(hours=24)
        
        for item in root.findall('.//item'):
            try:
                # Parse event details
                title = item.find('title').text or ""
                description = item.find('description').text or ""
                pub_date = item.find('pubDate').text
                
                # Parse datetime
                event_time = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %z')
                
                # Only include events in next 24 hours
                if now <= event_time <= next_24h:
                    # Extract impact level from description
                    impact = "Low"
                    if 'high-impact' in description.lower():
                        impact = "High"
                    elif 'medium-impact' in description.lower():
                        impact = "Medium"
                    
                    # Extract currency and event name
                    currency = None
                    event_name = title
                    
                    # Try to extract currency from title
                    for curr in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]:
                        if curr in title:
                            currency = curr
                            break
                    
                    events.append({
                        'time': event_time,
                        'title': title,
                        'impact': impact,
                        'currency': currency,
                        'description': description[:100] + "..." if len(description) > 100 else description
                    })
                    
            except Exception as e:
                logger.warning(f"Error parsing Forex Factory event: {e}")
                continue
        
        # Sort by time and return
        events.sort(key=lambda x: x['time'])
        return events[:10]  # Return top 10 events
        
    except Exception as e:
        logger.error(f"Error fetching Forex Factory events: {e}")
        return []

def get_news_awareness(instr):
    """
    Check if there are high-impact news events for this instrument's currencies
    Returns: (should_avoid_trading, events_list)
    """
    base_curr, quote_curr = pair_currencies(instr)
    events = fetch_forex_factory_events()
    
    relevant_events = []
    for event in events:
        if event['currency'] in [base_curr, quote_curr] and event['impact'] in ["High", "Medium"]:
            # Check if event is within next 30 minutes or just happened (last 15 minutes)
            event_time = event['time']
            now = datetime.now(timezone.utc)
            time_diff = (event_time - now).total_seconds() / 60  # in minutes
            
            # Avoid trading 15 minutes before to 15 minutes after high-impact events
            if -15 <= time_diff <= 30:
                relevant_events.append(event)
    
    should_avoid = len([e for e in relevant_events if e['impact'] == "High"]) > 0
    return should_avoid, relevant_events

def spread_liquidity_guard(instr, k=3.0):
    spr = spread_cache.get(instr, 0.0)
    hist = [v for ts,v in spread_history[instr] if time.time()-ts <= 3600]
    median = float(np.median(hist)) if hist else 0.0
    too_wide = (median>0 and spr > k*median)
    last_ts = spread_history[instr][-1][0] if spread_history[instr] else 0
    stale = (time.time() - last_ts) > 5
    return too_wide or stale, {"spread": spr, "median1h": median, "stale": stale}

# ========= LIQUIDITY & HTF ALIGNMENT HELPERS =========

def liquidity_factor(instr):
    """
    0..1 where 1 = very liquid (tight spreads, fresh ticks).
    Uses last-hour spread vs its own distribution + staleness penalty.
    """
    spr = float(spread_cache.get(instr, 0.0) or 0.0)
    hist = [v for ts, v in spread_history[instr] if time.time() - ts <= 3600]
    if not hist:
        return 0.5
    p50 = float(np.percentile(hist, 50))
    p90 = float(np.percentile(hist, 90))
    eps = 1e-12
    norm = 1.0 - ((spr - p50) / (p90 - p50 + eps))  # <= median → ~1; >= p90 → ~0
    norm = float(np.clip(norm, 0.0, 1.0))

    # staleness penalty (old ticks → less liquidity)
    last_ts = spread_history[instr][-1][0] if spread_history[instr] else 0
    stale_s = max(0.0, (time.time() - last_ts) - 2.0)  # seconds beyond 2s
    stale_penalty = float(np.clip(stale_s / 10.0, 0.0, 0.5))
    return float(np.clip(norm - stale_penalty, 0.0, 1.0))


def higher_tf_alignment(instr):
    """
    Returns alignment in [-1..+1].
    +1 if H1/H4/D1 all up, -1 if all down, else 0 (mixed).
    Uses EMA(12/26) on closes.
    """
    def _trend(df):
        if df is None or len(df) < 40:
            return 0
        ema_f = df["c"].ewm(span=12, adjust=False).mean().iloc[-1]
        ema_s = df["c"].ewm(span=26, adjust=False).mean().iloc[-1]
        return 1 if ema_f > ema_s else -1

    h1 = get_candles(instr, count=300, granularity="H1")
    h4 = get_candles(instr, count=300, granularity="H4")
    d1 = get_candles(instr, count=300, granularity="D")

    t1, t2, t3 = _trend(h1), _trend(h4), _trend(d1)
    if t1 == t2 == t3 == 1:
        return 1.0
    if t1 == t2 == t3 == -1:
        return -1.0
    return 0.0


def mtf_direction_vote(instr):
    """Return directional vote using M5/M15/H1 trend signs."""
    votes = {}
    for tf in ["M5", "M15", "H1"]:
        df = get_candles(instr, count=120, granularity=tf)
        if df is None or len(df) < 40:
            votes[tf] = 0
            continue
        ema_f = ema(df["c"], 10).iloc[-1]
        ema_s = ema(df["c"], 30).iloc[-1]
        votes[tf] = 1 if ema_f > ema_s else -1
    total = int(sum(votes.values()))
    return votes, (1 if total > 0 else -1 if total < 0 else 0)


def classify_regime_mode(regime_k, reg_intraday, atr_val, price):
    atrp = float(atr_val / (price + 1e-9))
    if reg_intraday == "high_vol" or atrp > 0.006:
        return "high_vol"
    if regime_k in ("trend", "trending") or reg_intraday == "trending":
        return "trend"
    return "range"


STRATEGY_CATALOG = {
    "BREAKOUT_SQUEEZE": {
        "impl": "Squeeze-Breakout",
        "sessions": {"LONDON", "NY", "OVERLAP"},
        "liquidity_min": 0.45,
        "regimes": {"trend", "high_vol"},
        "min_opportunity": 0.45,
        "fallback_exit": {"time_stop": TIME_STOP_BARS // 2, "trail": "atr"},
        "freq": "medium",
    },
    "TREND_PULLBACK": {
        "impl": "Trend-Pullback",
        "sessions": {"LONDON", "NY", "OVERLAP", "late_london"},
        "liquidity_min": 0.35,
        "regimes": {"trend", "high_vol"},
        "min_opportunity": 0.40,
        "fallback_exit": {"time_stop": TIME_STOP_BARS, "trail": "ema20"},
        "freq": "medium",
    },
    "RANGE_MEANREV": {
        "impl": "Range-MeanReversion",
        "sessions": {"ASIA", "DEAD_ZONE", "LONDON"},
        "liquidity_min": 0.30,
        "regimes": {"range", "low_vol"},
        "min_opportunity": 0.35,
        "fallback_exit": {"time_stop": TIME_STOP_BARS, "trail": "none"},
        "freq": "high",
    },
    "LIQUIDITY_SWEEP_REVERSAL": {
        "impl": "Liquidity-Sweep-Reversal",
        "sessions": {"ASIA", "LONDON", "NY", "OVERLAP"},
        "liquidity_min": 0.35,
        "regimes": {"range", "neutral", "low_vol"},
        "min_opportunity": 0.40,
        "fallback_exit": {"time_stop": TIME_STOP_BARS, "trail": "swing"},
        "freq": "low",
    },
}

STRATEGY_IMPL_TO_CODE = {v["impl"]: k for k, v in STRATEGY_CATALOG.items()}


def strategy_code_to_impl(code):
    return (STRATEGY_CATALOG.get(code) or {}).get("impl", code)


def strategy_impl_to_code(name):
    return STRATEGY_IMPL_TO_CODE.get(name, name)


def build_world_state(top_n=12):
    reset_daily_trade_budget_if_needed()
    refresh_pricing_once()
    nav, ccy = get_nav()
    open_positions = get_positions_info()
    var_est = portfolio_var(price_cache, horizon_days=1, cl=0.99)
    session = session_label()
    top = []
    by_instr = {}
    for ins in INSTRUMENTS:
        snap = build_market_snapshot(ins)
        if not snap:
            continue
        rv_short = float(snap["dfs"]["M5"]["c"].pct_change().rolling(20).std().iloc[-1] or 0.0)
        rv_long = float(snap["dfs"]["M5"]["c"].pct_change().rolling(200).std().iloc[-1] or 0.0)
        range_score = clamp01(1.0 - min(1.0, abs(snap["zscore"]) / 2.5))
        comp = float(snap.get("compression", 0.0))
        walls = snap.get("lux", {}).get("lux_meta", {})
        above = walls.get("above", [])
        below = walls.get("below", [])
        wall_above = float(above[0]["score"]) if above else 0.0
        wall_below = float(below[0]["score"]) if below else 0.0
        event_level = 1.0 if snap.get("event_block") else 0.0
        opp = clamp01(abs(snap.get("breakout", {}).get("mag", 0.0)) * 0.35 + abs(snap.get("zscore", 0.0))/3.0 * 0.25 + comp * 0.2 + abs(snap.get("lux", {}).get("lux_draw", 0.0))*0.2)
        top.append((ins, opp))
        by_instr[ins] = {
            "realized_vol_short": rv_short,
            "realized_vol_long": rv_long,
            "trend_strength": abs(float(snap.get("htf_align", 0.0))),
            "range_score": range_score,
            "compression_score": comp,
            "liquidity_factor": float(snap.get("liq_factor", 0.5)),
            "spread_percentile": float(snap.get("spread_info", {}).get("percentile", 50.0)),
            "tick_staleness": 1.0 if snap.get("spread_info", {}).get("stale") else 0.0,
            "wall_above_strength": wall_above,
            "wall_below_strength": wall_below,
            "session": session,
            "event_risk_level": event_level,
            "regime": snap.get("mode", "neutral"),
            "opportunity_score": opp,
            "snapshot": snap,
        }
    top = sorted(top, key=lambda x: x[1], reverse=True)
    top_instr = [k for k, _ in top[:top_n]]
    return {
        "ts": utc_now_iso(),
        "session": session,
        "market": {k: by_instr[k] for k in top_instr if k in by_instr},
        "portfolio": {
            "open_positions_count": len(open_positions),
            "portfolio_heat": current_portfolio_heat(nav),
            "currency_exposure": currency_exposure_map(),
            "trade_count_today": daily_trade_budget.get("trades_opened_today", 0),
            "realized_pnl_today": compute_day_realized_pnl(),
            "expectancy_proxy_7d": strategy_sharpe(),
            "var99": float(var_est.get("param", 0.0)),
            "nav": nav,
            "ccy": ccy,
        },
    }


def build_world_state_compact(world_state=None, top_n=10):
    ws = world_state or build_world_state(top_n=top_n)
    focus = sorted(ws["market"].items(), key=lambda kv: kv[1].get("opportunity_score", 0.0), reverse=True)[:top_n]
    events = fetch_econ_calendar() or []
    high_events = []
    now = datetime.now(timezone.utc)
    for e in events:
        if e.get("impact") != "High":
            continue
        when = e.get("time")
        mins = 9999
        if isinstance(when, datetime):
            mins = int((when - now).total_seconds() / 60)
        high_events.append({"currency": e.get("currency"), "event": e.get("event"), "mins": mins})
        if len(high_events) >= 5:
            break
    compact = {
        "timestamp": ws["ts"],
        "session": ws["session"],
        "trade_budget": {
            "trades_opened_today": daily_trade_budget.get("trades_opened_today", 0),
            "target_min": TRADE_TARGET_MIN,
            "target_max": TRADE_TARGET_MAX,
            "max_today": TRADE_HARD_MAX,
        },
        "portfolio": {
            "heat": round(ws["portfolio"].get("portfolio_heat", 0.0), 4),
            "var_gate": ws["portfolio"].get("var99", 0.0) <= VAR_LIMIT_PCT,
            "exposure_highlights": sorted(ws["portfolio"].get("currency_exposure", {}).items(), key=lambda x: abs(x[1]), reverse=True)[:2],
        },
        "events": high_events,
        "instruments": {},
    }
    for ins, m in focus:
        compact["instruments"][ins] = {
            "price": round(float(m["snapshot"]["mid"]), 5),
            "spread_pctile": round(float(m.get("spread_percentile", 50.0)), 2),
            "liquidity_factor": round(float(m.get("liquidity_factor", 0.5)), 3),
            "regime": m.get("regime", "neutral"),
            "compression_score": round(float(m.get("compression_score", 0.0)), 3),
            "breakout_mag": round(float(m["snapshot"].get("breakout", {}).get("mag", 0.0)), 3),
            "htf_align": round(float(m["snapshot"].get("htf_align", 0.0)), 3),
            "lux_draw": round(float(m["snapshot"].get("lux", {}).get("lux_draw", 0.0)), 3),
            "crowding_strength": round(float(m["snapshot"].get("pos_book", {}).get("crowding", 0.0)), 3),
            "recent_strategy_results": {
                k: round(float(np.mean(list(v)[-10:])) if len(v) else 0.0, 3) for k, v in strategy_perf.items()
            },
        }
    return compact


def score_strategy_for_market(code, market, session):
    snap = market["snapshot"]
    comp = market.get("compression_score", 0.0)
    trend = market.get("trend_strength", 0.0)
    liq = market.get("liquidity_factor", 0.5)
    range_score = market.get("range_score", 0.0)
    lux = abs(float(snap.get("lux", {}).get("lux_draw", 0.0)))
    breakout = abs(float(snap.get("breakout", {}).get("mag", 0.0)))
    crowd = abs(float(snap.get("pos_book", {}).get("crowding", 0.0)))
    vol_ratio = market.get("realized_vol_short", 0.0) / (market.get("realized_vol_long", 1e-9) + 1e-9)

    if code == "BREAKOUT_SQUEEZE":
        return 0.30 * comp + 0.20 * min(1.0, breakout) + 0.20 * trend + 0.20 * liq + (0.10 if session in {"LONDON", "NY", "OVERLAP"} else 0.0) + 0.10 * min(1.0, vol_ratio)
    if code == "TREND_PULLBACK":
        pullback = 1.0 - min(1.0, abs((snap.get("mid", 0.0) - snap.get("ema20", 0.0)) / (snap.get("atr", 1e-9) + 1e-9)) / 2.0)
        return 0.35 * trend + 0.25 * pullback + 0.20 * liq + 0.20 * market.get("opportunity_score", 0.0)
    if code == "RANGE_MEANREV":
        mixed = 1.0 - trend
        return 0.35 * range_score + 0.25 * mixed + 0.20 * max(0.0, 1.0 - vol_ratio) + 0.20 * (0.8 if session == "ASIA" else 0.4)
    if code == "LIQUIDITY_SWEEP_REVERSAL":
        walls = clamp01(market.get("wall_above_strength", 0.0) + market.get("wall_below_strength", 0.0))
        return 0.35 * lux + 0.25 * walls + 0.20 * crowd + 0.20 * range_score
    return 0.0


def sample_bandit_weight(session, strategy_code):
    arm = bandit_state[session][strategy_code]
    return float(np.random.beta(arm["alpha"], arm["beta"]))


def update_bandit_reward(session, strategy_code, reward_r):
    arm = bandit_state[session][strategy_code]
    r = float(np.clip(reward_r, -1.0, 1.0))
    p = (r + 1.0) / 2.0
    arm["alpha"] += p
    arm["beta"] += (1.0 - p)


def build_deterministic_director_decision(world_state):
    decision = {"focus": [], "quota_plan": {"mode": "normal", "notes": ""}, "global_notes": []}
    session = world_state["session"]
    for ins, market in world_state["market"].items():
        scores = {}
        for code, cfg in STRATEGY_CATALOG.items():
            if session not in cfg["sessions"] and not (session == "LONDON" and "late_london" in cfg["sessions"]):
                continue
            if market["liquidity_factor"] < cfg["liquidity_min"]:
                continue
            if market["regime"] not in cfg["regimes"]:
                continue
            rule = score_strategy_for_market(code, market, session)
            band = sample_bandit_weight(session, code)
            final = rule * (0.7 + 0.3 * band)
            if final >= cfg["min_opportunity"]:
                scores[code] = {"rule": rule, "bandit": band, "final": final}
        ranked = sorted(scores.items(), key=lambda kv: kv[1]["final"], reverse=True)
        if not ranked:
            continue
        selected = [r[0] for r in ranked[:2]]
        raw = [max(1e-6, ranked[i][1]["final"]) for i in range(len(selected))]
        tot = sum(raw)
        weights = {selected[i]: raw[i] / tot for i in range(len(selected))}
        decision["focus"].append({
            "instrument": ins,
            "strategies": selected,
            "strategy_weights": weights,
            "priority": clamp01(ranked[0][1]["final"]),
            "confidence": clamp01(np.mean([x[1]["final"] for x in ranked[:2]])),
            "reasons": [f"{k}:{round(v['final'],3)}" for k, v in ranked[:3]],
        })
    decision["focus"] = sorted(decision["focus"], key=lambda x: x["priority"], reverse=True)
    decision["focus"] = decision["focus"][:DIRECTOR_TOP_FOCUS]
    opened = daily_trade_budget.get("trades_opened_today", 0)
    mode = "normal"
    if opened < TRADE_TARGET_MIN and datetime.now(timezone.utc).hour >= 12:
        mode = "expand_breadth"
        if datetime.now(timezone.utc).hour >= 16 and opened == 0:
            mode = "scalp_mode"
    decision["quota_plan"] = {"mode": mode, "notes": "ladder_breadth_only"}
    return decision


def currency_exposure_map():
    nav, _ = get_nav()
    expo = defaultdict(float)
    for ins in INSTRUMENTS:
        b, q = pair_currencies(ins)
        px = float(price_cache.get(ins, 0.0) or 0.0)
        for t in get_open_trades(ins):
            u = float(t.get("currentUnits", 0.0) or 0.0)
            notion = abs(u * px)
            sign = 1.0 if u > 0 else -1.0
            expo[b] += sign * notion
            expo[q] -= sign * notion
    if nav <= 0:
        return dict(expo)
    return {k: v / nav for k, v in expo.items()}


def compute_day_realized_pnl():
    tx = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/transactions") or {}
    rows = [t for t in tx.get("transactions", []) if t.get("type") == "ORDER_FILL"]
    if not rows:
        return 0.0
    now = datetime.now(timezone.utc).date().isoformat()
    total = 0.0
    for t in rows[-300:]:
        ts = (t.get("time") or "")[:10]
        if ts != now:
            continue
        total += float(t.get("pl", 0.0) or 0.0)
    return total


def openrouter_headers():
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = OPENROUTER_SITE_URL
    if OPENROUTER_APP_NAME:
        headers["X-Title"] = OPENROUTER_APP_NAME
    return headers


async def openrouter_chat(messages, cache_key):
    if not OPENROUTER_API_KEY:
        return None
    now = time.time()
    c = openrouter_state["cache"].get(cache_key)
    if c and now - c["ts"] < 120:
        return c["data"]
    if now - openrouter_state.get("last_call", 0.0) < OPENROUTER_COOLDOWN_SEC:
        return None
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": OPENROUTER_MAX_TOKENS,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    url = "https://openrouter.ai/api/v1/chat/completions"
    for _ in range(2):
        try:
            resp = await asyncio.to_thread(requests.post, url, headers=openrouter_headers(), data=json.dumps(payload), timeout=OPENROUTER_TIMEOUT_SEC)
            openrouter_state["last_call"] = time.time()
            if resp.status_code >= 400:
                continue
            j = resp.json()
            content = (((j.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}")
            data = json.loads(content)
            openrouter_state["cache"][cache_key] = {"ts": time.time(), "data": data}
            return data
        except Exception:
            continue
    return None


def validate_llm_decision(data, allowed_instruments):
    if not isinstance(data, dict):
        return None
    out = {"focus": [], "quota_plan": {"mode": "normal", "notes": ""}, "global_notes": []}
    mode = ((data.get("quota_plan") or {}).get("mode") or "normal")
    if mode not in {"normal", "expand_breadth", "scalp_mode"}:
        mode = "normal"
    out["quota_plan"] = {"mode": mode, "notes": str((data.get("quota_plan") or {}).get("notes") or "")[:120]}
    for item in (data.get("focus") or [])[:5]:
        ins = item.get("instrument")
        if ins not in allowed_instruments:
            continue
        strats = [s for s in (item.get("strategies") or []) if s in STRATEGY_CATALOG][:2]
        if not strats:
            continue
        out["focus"].append({
            "instrument": ins,
            "strategies": strats,
            "priority": clamp01(item.get("priority", 0.5)),
            "confidence": clamp01(item.get("confidence", 0.5)),
            "reasons": [str(r)[:40] for r in (item.get("reasons") or [])[:5]],
        })
    out["global_notes"] = [str(x)[:60] for x in (data.get("global_notes") or [])[:5]]
    return out


async def maybe_llm_director(world_state, deterministic):
    compact = build_world_state_compact(world_state)
    payload = json.dumps(compact, sort_keys=True)
    key = hashlib.sha1((payload + str(daily_trade_budget.get("trades_opened_today", 0)) + world_state["session"]).encode()).hexdigest()[:18]
    msgs = [
        {"role": "system", "content": "You are a strategy director. Choose strategies, not trades. Return JSON only in exact schema. Never override risk gates."},
        {"role": "user", "content": json.dumps({"world_state": compact, "allowed_strategies": list(STRATEGY_CATALOG.keys()), "rules": "Aim for 2-3 trades/day via best setups; if low opportunity choose expand_breadth."})},
    ]
    llm = await openrouter_chat(msgs, key)
    valid = validate_llm_decision(llm, set(world_state["market"].keys())) if llm else None
    if valid:
        return valid, True
    return deterministic, False


def strategy_candidates(instr, df, sigs, score):
    direction = 1 if score >= 0 else -1
    rev_dir = -1 if sigs.get("meanrev", 0.0) > 0 else 1
    return [
        {
            "name": "Breakout-Squeeze",
            "direction": direction,
            "entry_type": "STOP",
            "confidence": abs(0.7 * sigs.get("breakout", 0.0) + 0.3 * sigs.get("compression", 0.0)),
            "validity_window": 3,
        },
        {
            "name": "Range-MeanReversion",
            "direction": rev_dir,
            "entry_type": "LIMIT",
            "confidence": abs(sigs.get("meanrev", 0.0)) * (1.0 + max(0.0, sigs.get("lux_draw", 0.0))),
            "validity_window": 6,
        },
        {
            "name": "Liquidity-Draw/Sweep",
            "direction": 1 if sigs.get("lux_draw", 0.0) >= 0 else -1,
            "entry_type": "MARKET",
            "confidence": abs(sigs.get("lux_draw", 0.0)),
            "validity_window": 4,
        },
    ]


def select_best_strategy(instr, df, sigs, score, mode):
    cands = strategy_candidates(instr, df, sigs, score)
    mode_bias = {
        "trend": {"Breakout-Squeeze": 1.2, "Range-MeanReversion": 0.8, "Liquidity-Draw/Sweep": 1.0},
        "range": {"Breakout-Squeeze": 0.8, "Range-MeanReversion": 1.2, "Liquidity-Draw/Sweep": 1.05},
        "high_vol": {"Breakout-Squeeze": 1.1, "Range-MeanReversion": 0.7, "Liquidity-Draw/Sweep": 1.0},
    }
    for c in cands:
        perf = strategy_perf[c["name"]]
        expectancy = np.mean(perf) if perf else 0.0
        c["meta_score"] = c["confidence"] * mode_bias.get(mode, {}).get(c["name"], 1.0) + 0.05 * expectancy
    return max(cands, key=lambda x: x["meta_score"]) if cands else None


def spread_percentile_guard(instr):
    spr = float(spread_cache.get(instr, 0.0) or 0.0)
    hist = [v for ts, v in spread_history[instr] if time.time() - ts <= 3600]
    if len(hist) < 25:
        return False, {"spread": spr, "percentile": 50.0}
    pctl = float((np.sum(np.array(hist) <= spr) / len(hist)) * 100.0)
    return pctl >= SPREAD_GUARD_PCTL, {"spread": spr, "percentile": pctl}


def atr_spike_guard(df):
    atr_series = atr(df, ATR_PERIOD).dropna()
    if len(atr_series) < 50:
        return False, {"atr": 0.0, "atr_med": 0.0, "multiple": 0.0}
    now = float(atr_series.iloc[-1])
    med = float(atr_series.tail(50).median())
    mult = now / (med + 1e-9)
    return mult >= ATR_SPIKE_MULT, {"atr": now, "atr_med": med, "multiple": mult}


def event_guardrails_strict(instr):
    base, quote = pair_currencies(instr)
    events = fetch_econ_calendar() or []
    now = datetime.now(timezone.utc)
    for e in events:
        ccy = e.get("currency", "")
        if ccy not in (base, quote):
            continue
        impact = str(e.get("impact", "")).lower()
        if impact not in ("high", "medium", "3", "2"):
            continue
        when = e.get("when") or e.get("time")
        try:
            t = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
        except Exception:
            continue
        mins = (t - now).total_seconds() / 60.0
        if -EVENT_POST_BUFFER_MIN <= mins <= EVENT_PRE_BUFFER_MIN:
            return True
    return False


def signal_id(instr, direction, setup_type, level):
    bucket = int(time.time() // (SIGNAL_ID_TTL_MIN * 60))
    raw = f"{instr}|{direction}|{setup_type}|{round(float(level),5)}|{bucket}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def signal_id_seen(sig_id):
    now = time.time()
    expired = [k for k, ts in executed_signal_ids.items() if now - ts > SIGNAL_ID_TTL_MIN * 60]
    for k in expired:
        executed_signal_ids.pop(k, None)
    if sig_id in executed_signal_ids:
        return True
    executed_signal_ids[sig_id] = now
    return False


def idea_dedup_block(instr, direction):
    ts, prev_dir = signal_dedup_state.get(instr, (0.0, 0))
    bars_elapsed = (time.time() - ts) / max(COOLDOWN_SEC, 1)
    if prev_dir == direction and bars_elapsed < IDEA_DEDUP_BARS:
        return True
    signal_dedup_state[instr] = (time.time(), direction)
    return False


def strategy_enabled(name):
    until = float(strategy_disable_until.get(name, 0.0) or 0.0)
    if time.time() < until:
        return False
    perf = strategy_perf[name]
    if len(perf) < RISK_CUTOFF_EXPECTANCY_TRADES:
        return True
    tail = list(perf)[-RISK_CUTOFF_EXPECTANCY_TRADES:]
    return float(np.mean(tail)) >= 0.0


def current_portfolio_heat(nav):
    heat = 0.0
    for ins in INSTRUMENTS:
        for t in get_open_trades(ins):
            ep = float(t.get("price", 0.0) or 0.0)
            sl = float((t.get("stopLossOrder") or {}).get("price", ep))
            u = abs(float(t.get("currentUnits", 0.0) or 0.0))
            heat += abs(ep - sl) * u
    return heat / (nav + 1e-9)


def currency_cluster_exposure_pct(nav, direction, instr):
    base, quote = pair_currencies(instr)
    cluster = {base, quote}
    exp = 0.0
    for ins in INSTRUMENTS:
        b, q = pair_currencies(ins)
        if not ({b, q} & cluster):
            continue
        for t in get_open_trades(ins):
            u = float(t.get("currentUnits", 0.0) or 0.0)
            mid = float(price_cache.get(ins, 0.0) or 0.0)
            exp += abs(u * mid)
    return exp / (nav + 1e-9)


def update_daily_risk_state(nav):
    d = datetime.now(timezone.utc).date().isoformat()
    if daily_risk_state["day"] != d:
        daily_risk_state.update({"day": d, "start_nav": nav, "peak_nav": nav, "kill": False})
    daily_risk_state["peak_nav"] = max(float(daily_risk_state.get("peak_nav") or nav), nav)


def daily_kill_switch_triggered(nav):
    update_daily_risk_state(nav)
    start = float(daily_risk_state.get("start_nav") or nav)
    peak = float(daily_risk_state.get("peak_nav") or nav)
    if start <= 0:
        return False, {}
    realized_dd = (nav - start) / start
    intraday_dd = (nav - peak) / peak if peak > 0 else 0.0
    kill = realized_dd <= -DAILY_LOSS_LIMIT_PCT or intraday_dd <= -DAILY_DD_KILL_PCT
    daily_risk_state["kill"] = kill
    return kill, {"from_start": realized_dd, "from_peak": intraday_dd}


def log_feature_attribution(instr, strategy_name, regime_mode, entry_type, score, sigs, spread_info, atr_info):
    feature_attribution_log.append({
        "ts": utc_now_iso(),
        "instr": instr,
        "strategy": strategy_name,
        "regime_mode": regime_mode,
        "entry_type": entry_type,
        "score": float(score),
        "spread": float(spread_info.get("spread", 0.0)),
        "spread_pct": float(spread_info.get("percentile", 0.0)),
        "atr_mult": float(atr_info.get("multiple", 0.0)),
        "breakout": float(sigs.get("breakout", 0.0)),
        "meanrev": float(sigs.get("meanrev", 0.0)),
        "lux_draw": float(sigs.get("lux_draw", 0.0)),
    })


def make_trade_plan(instrument, strategy, side, order_type, entry, sl, tp, time_stop_bars, confidence, pwin, ev_r, validity_sec, metadata=None):
    rr = abs(tp - entry) / max(abs(entry - sl), 1e-9)
    return {
        "instrument": instrument,
        "strategy": strategy,
        "side": side,
        "order_type": order_type,
        "entry_price": float(entry),
        "stop_loss": float(sl),
        "take_profit": float(tp),
        "time_stop_bars": int(time_stop_bars),
        "confidence": float(np.clip(confidence, 0.0, 1.0)),
        "pwin": float(np.clip(pwin, 0.0, 1.0)),
        "ev_r": float(ev_r),
        "rr": float(rr),
        "validity_sec": int(validity_sec),
        "ts": time.time(),
        "meta": metadata or {},
        "strategy_id": strategy,
        "direction": 1 if side == "BUY" else -1,
        "entry_type": order_type.lower(),
        "expected_RR": float(rr),
        "calibrated_pwin": float(np.clip(pwin, 0.0, 1.0)),
        "expected_value_proxy": float(ev_r),
        "liquidity_factor": float((metadata or {}).get("liq_factor", 0.0)),
        "spread_pctile": float((metadata or {}).get("spread_pctile", 50.0)),
        "risk_cost": 0.0,
        "reason_codes": list((metadata or {}).get("reason_codes", [])),
    }


def build_market_snapshot(instr):
    refresh_pricing_once()
    m5 = get_candles(instr, count=500, granularity="M5")
    m15 = get_candles(instr, count=300, granularity="M15")
    h1 = get_candles(instr, count=300, granularity="H1")
    if m5 is None or m15 is None or h1 is None or len(m5) < 120:
        return None
    mid = float(price_cache.get(instr, m5["c"].iloc[-1]))
    atr_val = float(atr(m5, ATR_PERIOD).iloc[-1] or 0.0)
    atr_pct = float(atr_val / (mid + 1e-9))
    ema20 = float(ema(m5["c"], 20).iloc[-1])
    ema50 = float(ema(m5["c"], 50).iloc[-1])
    z = float(zscore(m5["c"], lookback=min(200, len(m5))).iloc[-1]) if len(m5) > 50 else 0.0
    comp_s, _ = compression_score(m5["c"], n=BBANDS_N, q=SQUEEZE_Q)
    brk_dir, brk_lvl, brk_mag = breakout_signal(m5, n=DONCHIAN_N)
    lux = lux_draw_on_liquidity(
        m5,
        length=LIQ_SW_LENGTH,
        area_mode="full" if LIQ_SW_AREA.lower().startswith("full") else "wick",
        filter_by="volume" if LIQ_SW_FILTER.lower().startswith("vol") else "count",
        threshold=LIQ_SW_THRESHOLD,
    )
    reg_intraday, risk_mult = compute_intraday_regime(m5)
    mode = classify_regime_mode(reg_intraday, reg_intraday, atr_val, mid)
    spr_block, spr_info = spread_liquidity_guard(instr)
    liq = liquidity_factor(instr)
    return {
        "instrument": instr,
        "mid": mid,
        "spread": float(spread_cache.get(instr, 0.0) or 0.0),
        "dfs": {"M5": m5, "M15": m15, "H1": h1},
        "atr": atr_val,
        "atr_pct": atr_pct,
        "ema20": ema20,
        "ema50": ema50,
        "zscore": z,
        "compression": float(comp_s),
        "breakout": {"dir": int(brk_dir), "level": float(brk_lvl), "mag": float(brk_mag)},
        "lux": lux,
        "regime": reg_intraday,
        "mode": mode,
        "risk_mult": float(risk_mult),
        "spread_block": bool(spr_block),
        "spread_info": spr_info,
        "liq_factor": float(liq),
        "event_block": bool(event_guardrails(instr) or event_guardrails_strict(instr)),
        "mtf_votes": mtf_direction_vote(instr)[0],
        "created_ts": time.time(),
    }


def strategy_trend_pullback(snapshot):
    m5, m15, h1 = snapshot["dfs"]["M5"], snapshot["dfs"]["M15"], snapshot["dfs"]["H1"]
    e15f, e15s = ema(m15["c"], 10).iloc[-1], ema(m15["c"], 30).iloc[-1]
    eh1f, eh1s = ema(h1["c"], 10).iloc[-1], ema(h1["c"], 30).iloc[-1]
    trend_dir = 1 if (e15f > e15s and eh1f > eh1s) else -1 if (e15f < e15s and eh1f < eh1s) else 0
    if trend_dir == 0 or snapshot["event_block"] or snapshot["spread_block"]:
        return None
    pullback_zone = ema(m5["c"], 20).iloc[-1] if trend_dir > 0 else ema(m5["c"], 20).iloc[-1]
    near_pullback = abs(snapshot["mid"] - pullback_zone) <= 0.8 * snapshot["atr"]
    if not near_pullback:
        return None
    entry = float(pullback_zone)
    sl = entry - 1.6 * snapshot["atr"] if trend_dir > 0 else entry + 1.6 * snapshot["atr"]
    tp = entry + 2.0 * abs(entry - sl) if trend_dir > 0 else entry - 2.0 * abs(entry - sl)
    confidence = min(1.0, 0.55 + 0.25 * snapshot["liq_factor"])
    pwin = min(0.85, 0.50 + 0.20 * confidence)
    evr = pwin * 2.0 - (1 - pwin)
    return make_trade_plan(snapshot["instrument"], "Trend-Pullback", "BUY" if trend_dir > 0 else "SELL", "LIMIT" if near_pullback else "MARKET", entry, sl, tp, TIME_STOP_BARS, confidence, pwin, evr, COOLDOWN_SEC * 2, {"trend_dir": trend_dir})


def strategy_squeeze_breakout(snapshot):
    brk = snapshot["breakout"]
    if snapshot["event_block"] or snapshot["spread_block"]:
        return None
    if snapshot["compression"] < 0.70 or abs(brk["dir"]) == 0 or brk["mag"] < 0.2:
        return None
    h1 = snapshot["mtf_votes"].get("H1", 0)
    if h1 == -brk["dir"]:
        return None
    entry = brk["level"]
    sl = entry - 1.8 * snapshot["atr"] if brk["dir"] > 0 else entry + 1.8 * snapshot["atr"]
    tp = entry + 2.5 * abs(entry - sl) if brk["dir"] > 0 else entry - 2.5 * abs(entry - sl)
    confidence = min(1.0, 0.45 + 0.35 * snapshot["compression"] + 0.2 * min(1.0, brk["mag"]))
    pwin = min(0.75, 0.45 + 0.15 * confidence)
    evr = pwin * 2.5 - (1 - pwin)
    return make_trade_plan(snapshot["instrument"], "Squeeze-Breakout", "BUY" if brk["dir"] > 0 else "SELL", "STOP", entry, sl, tp, max(6, TIME_STOP_BARS // 2), confidence, pwin, evr, COOLDOWN_SEC * 2, {"compression": snapshot["compression"], "brk_mag": brk["mag"]})


def strategy_range_mean_reversion(snapshot):
    if snapshot["mode"] not in ("range", "low_vol"):
        return None
    if snapshot["event_block"] or snapshot["spread_block"]:
        return None
    z = snapshot["zscore"]
    if abs(z) < 1.3:
        return None
    side = -1 if z > 0 else 1
    entry = snapshot["mid"]
    sl = entry - 1.4 * snapshot["atr"] if side > 0 else entry + 1.4 * snapshot["atr"]
    tp = snapshot["ema20"]
    confidence = min(1.0, 0.50 + 0.15 * min(2.5, abs(z)) / 2.5 + 0.2 * snapshot["liq_factor"])
    pwin = min(0.82, 0.52 + 0.18 * confidence)
    rr = abs(tp - entry) / max(abs(entry - sl), 1e-9)
    evr = pwin * rr - (1 - pwin)
    return make_trade_plan(snapshot["instrument"], "Range-MeanReversion", "BUY" if side > 0 else "SELL", "LIMIT", entry, sl, tp, TIME_STOP_BARS, confidence, pwin, evr, COOLDOWN_SEC * 2, {"zscore": z})


def strategy_liquidity_sweep(snapshot):
    if snapshot["mode"] not in ("range", "neutral"):
        return None
    draw = float(snapshot["lux"].get("lux_draw", 0.0) or 0.0)
    if abs(draw) < 0.35 or snapshot["event_block"]:
        return None
    side = 1 if draw < 0 else -1
    entry = snapshot["mid"]
    sl = entry - 1.5 * snapshot["atr"] if side > 0 else entry + 1.5 * snapshot["atr"]
    tp = entry + 1.8 * abs(entry - sl) if side > 0 else entry - 1.8 * abs(entry - sl)
    confidence = min(1.0, 0.45 + 0.4 * abs(draw))
    pwin = min(0.78, 0.48 + 0.2 * confidence)
    evr = pwin * 1.8 - (1 - pwin)
    return make_trade_plan(snapshot["instrument"], "Liquidity-Sweep-Reversal", "BUY" if side > 0 else "SELL", "MARKET", entry, sl, tp, TIME_STOP_BARS, confidence, pwin, evr, COOLDOWN_SEC * 2, {"lux_draw": draw})


def candidate_plans_from_snapshot(snapshot, allowed_impl=None):
    cands = []
    fn_map = {
        "Trend-Pullback": strategy_trend_pullback,
        "Squeeze-Breakout": strategy_squeeze_breakout,
        "Range-MeanReversion": strategy_range_mean_reversion,
        "Liquidity-Sweep-Reversal": strategy_liquidity_sweep,
    }
    selected = allowed_impl or list(fn_map.keys())
    for name in selected:
        fn = fn_map.get(name)
        if not fn:
            continue
        try:
            p = fn(snapshot)
            if p:
                cands.append(p)
        except Exception as e:
            log_event("INFO", snapshot["instrument"], f"strategy {fn.__name__} failed", {"err": str(e)}, level=1)
    return cands


def plan_passes_gates(plan, snapshot):
    if daily_trade_budget.get("trades_opened_today", 0) >= TRADE_HARD_MAX:
        return False, "DailyMax"
    chop = snapshot.get("atr_pct", 0.0) < 0.0015 and abs(snapshot.get("htf_align", 0.0)) < 0.2 and snapshot.get("spread_info", {}).get("percentile", 50) > 80
    if chop and "Range" not in plan.get("strategy", ""):
        return False, "Chop"
    if plan["rr"] < MIN_PLAN_RR:
        return False, "RR"
    if plan["ev_r"] < MIN_PLAN_EVR:
        return False, "EV"
    if snapshot["event_block"]:
        return False, "Event"
    spr_pct_block, _ = spread_percentile_guard(plan["instrument"])
    if spr_pct_block or snapshot["spread_block"]:
        return False, "Spread"
    return True, "OK"


def strategy_router(instr, snapshot, allowed_impl=None):
    plans = candidate_plans_from_snapshot(snapshot, allowed_impl=allowed_impl)
    debug = []
    survivors = []
    for p in plans:
        ok, reason = plan_passes_gates(p, snapshot)
        debug.append({"strategy": p["strategy"], "ev_r": p["ev_r"], "rr": p["rr"], "confidence": p["confidence"], "gate": reason})
        if ok and strategy_enabled(p["strategy"]):
            mismatch_penalty = 0.9 if (snapshot["mode"] == "trend" and "Range" in p["strategy"]) else 1.0
            p["rank"] = p["ev_r"] * p["confidence"] * snapshot["liq_factor"] * mismatch_penalty
            survivors.append(p)
    chosen = max(survivors, key=lambda x: x["rank"]) if survivors else None
    log_event("DECISION", instr, "Plan candidates", {"regime": snapshot["regime"], "plans": debug, "chosen": (chosen or {}).get("strategy")}, level=2)
    return chosen, debug


def plan_id(plan):
    bucket = int(time.time() // (SIGNAL_ID_TTL_MIN * 60))
    raw = f"{plan['instrument']}|{plan['strategy']}|{plan['side']}|{round(plan['entry_price'],5)}|{bucket}"
    return hashlib.sha1(raw.encode()).hexdigest()[:18]


def plan_seen_recently(pid):
    now = time.time()
    exp = [k for k, ts in recent_plan_ids.items() if now - ts > SIGNAL_ID_TTL_MIN * 60]
    for k in exp:
        recent_plan_ids.pop(k, None)
    if pid in recent_plan_ids:
        return True
    recent_plan_ids[pid] = now
    return False


def place_limit_entry_order(instr, units, price, tp=None, sl=None):
    order = {
        "order": {
            "units": str(units),
            "instrument": instr,
            "price": f"{_round_price(instr, price)}",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "positionFill": "DEFAULT"
        }
    }
    if tp is not None:
        order["order"]["takeProfitOnFill"] = {"price": f"{tp}"}
    if sl is not None:
        order["order"]["stopLossOnFill"] = {"price": f"{sl}"}
    return safe_post(f"{HOST}/accounts/{OANDA_ACCOUNTID}/orders", json_data=order)


def risk_approve_and_size(plan, snapshot, trade_prep=None):
    nav, _ = get_nav()
    heat = current_portfolio_heat(nav)
    if heat >= PORTFOLIO_HEAT_LIMIT:
        return None, {"blocked": "heat", "heat": heat}
    cluster = currency_cluster_exposure_pct(nav, 1 if plan["side"] == "BUY" else -1, plan["instrument"])
    if cluster >= CLUSTER_HEAT_LIMIT:
        return None, {"blocked": "cluster", "cluster": cluster}
    direction = 1 if plan["side"] == "BUY" else -1
    units = units_from_risk(plan["instrument"], snapshot["mid"], snapshot["atr"], direction)
    conf_mult = 0.6 + 0.8 * plan["confidence"]
    if daily_trade_budget.get("consecutive_losses", 0) >= 3:
        if plan.get("confidence", 0.0) < 0.65:
            return None, {"blocked": "revenge_filter", "loss_streak": daily_trade_budget.get("consecutive_losses", 0)}
        conf_mult *= 0.65
    regime_mult = 0.6 if snapshot["mode"] == "high_vol" else 1.0
    corr_pen = max(0.4, 1.0 - min(0.6, cluster * 10.0))
    units = int(units * conf_mult * regime_mult * corr_pen * snapshot.get("risk_mult", 1.0))
    intel_mult = 1.0
    if trade_prep and getattr(trade_prep.get("sizing_decision"), "recommended_risk_fraction", None) is not None:
        sd = trade_prep["sizing_decision"]
        base_rf = max(float(getattr(sd, "base_risk_fraction", ACCOUNT_RISK_PCT)), 1e-9)
        intel_mult = float(getattr(sd, "recommended_risk_fraction", base_rf)) / base_rf
        units = int(units * intel_mult)
    units = realized_vol_target(units, snapshot["dfs"]["M5"])
    if units == 0:
        return None, {"blocked": "units_zero"}

    corr_lookup = {}
    for row in (correlation_matrix().get("top", []) + correlation_matrix().get("bottom", [])):
        pair = row.get("pair", "")
        if "-" in pair:
            a, b = pair.split("-")
            corr_lookup.setdefault(a, {})[b] = row.get("corr", 0.0)
            corr_lookup.setdefault(b, {})[a] = row.get("corr", 0.0)

    signed_units = int(units * direction)
    open_positions = [{"instrument": t.get("instrument"), "units": float(t.get("currentUnits", 0.0))} for t in get_open_trades()]
    assessed = apply_portfolio_caps({**plan, "signed_units": signed_units}, open_positions, nav, corr_lookup, portfolio_limits)
    if assessed.get("blocked"):
        return None, {"blocked": "portfolio_caps", **assessed}

    plan2 = dict(plan)
    plan2["units"] = units
    plan2["risk_cost"] = assessed.get("risk_cost", 0.0)
    plan2["correlation_cluster_id"] = assessed.get("correlation_cluster_id", "OTHER")
    plan2["risk_diag"] = {"heat": heat, "cluster": cluster, "conf_mult": conf_mult, "regime_mult": regime_mult, "corr_pen": corr_pen, "intel_mult": intel_mult, "risk_cost": plan2["risk_cost"]}
    return plan2, plan2["risk_diag"]


def execute_trade_plan(plan, snapshot):
    pid = plan_id(plan)
    if plan_seen_recently(pid):
        return None, {"skip": "duplicate_plan", "plan_id": pid}
    direction = 1 if plan["side"] == "BUY" else -1
    units = abs(int(plan["units"])) * direction
    entry = float(plan["entry_price"])
    sl = _round_price(plan["instrument"], plan["stop_loss"])
    tp = _round_price(plan["instrument"], plan["take_profit"])
    true_entry = entry if plan["order_type"] in ("STOP", "LIMIT") else snapshot["mid"]
    rr = abs(tp - true_entry) / max(abs(true_entry - sl), 1e-9)
    if rr < MIN_PLAN_RR:
        return None, {"skip": "rr_invalid", "rr": rr}

    pctl_block, pctl_info = spread_percentile_guard(plan["instrument"])
    spread_pctile = float(pctl_info.get("percentile", 50.0))
    order_type = choose_entry_type(plan.get("strategy", ""), float(snapshot.get("breakout", {}).get("mag", 0.0)), float(snapshot.get("liq_factor", 0.0)), spread_pctile)
    if plan["order_type"] == "STOP":
        order_type = "STOP"
    if pctl_block and order_type == "MARKET":
        order_type = "LIMIT"

    staging = clip_staging_plan(units, float(snapshot.get("liq_factor", 0.0)), bool(snapshot.get("event_block", False)))
    resp = None
    for clip in staging:
        if clip == 0:
            continue
        if order_type == "STOP":
            resp = place_stop_entry_order(plan["instrument"], clip, price=entry, tp=tp, sl=sl)
        elif order_type == "LIMIT":
            resp = place_limit_entry_order(plan["instrument"], clip, price=entry, tp=tp, sl=sl)
        else:
            resp = place_market_order(plan["instrument"], clip, tp=tp, sl=sl)

    latest_plan_cache[plan["instrument"]] = {**plan, "plan_id": pid, "exec_ts": utc_now_iso(), "rr_exec": rr, "order_type_exec": order_type, "clips": len(staging)}
    return resp, {"plan_id": pid, "rr": rr, "order_type_exec": order_type, "clips": len(staging), "spread_pctile": spread_pctile}


def lifecycle_manager(sl_buffer=0.04):
    for instr in INSTRUMENTS:
        manage_active_trades(instr, sl_buffer=sl_buffer)


def update_strategy_performance_from_fills():
    global last_tx_seen
    tx = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/transactions") or {}
    rows = [t for t in tx.get("transactions", []) if t.get("type") == "ORDER_FILL"]
    if not rows:
        return
    rows = sorted(rows, key=lambda x: int(x.get("id", 0)))
    for t in rows:
        tid = str(t.get("id"))
        if last_tx_seen is not None and int(tid) <= int(last_tx_seen):
            continue
        pl = float(t.get("pl", 0.0) or 0.0)
        trade_closed = t.get("tradeReduced") or t.get("tradesClosed")
        if not trade_closed:
            continue
        instr = t.get("instrument", "")
        plan = latest_plan_cache.get(instr, {})
        strat = plan.get("strategy", "Unknown")
        risk = abs(float(plan.get("entry_price", 0.0)) - float(plan.get("stop_loss", 0.0)))
        units = abs(float(plan.get("units", 0.0) or 0.0))
        r = pl / max(risk * max(units, 1.0), 1e-9)
        edge_monitor.update(strat, r)
        decayed, edge_diag = edge_monitor.edge_decayed(strat, min_trades=RISK_CUTOFF_EXPECTANCY_TRADES)
        if decayed:
            strategy_disable_until[strat] = time.time() + STRAT_DISABLE_COOLDOWN_MIN * 60
            log_event("RISK", instr, f"Edge decay kill-switch for {strat}", edge_diag, level=1)
        fill_px = float(t.get("price", plan.get("entry_price", 0.0)) or 0.0)
        execution_stats.record_fill(instr, float(spread_cache.get(instr, 0.0) or 0.0), float(plan.get("entry_price", fill_px) or fill_px), fill_px)
        intel_tid = plan.get("trade_intel_id")
        if intel_tid:
            closed_meta = (t.get("tradesClosed") or [{}])[0]
            closed_id = str(closed_meta.get("tradeID", ""))
            opened_ts = float((trade_entry_meta.get(closed_id, {}) or {}).get("ts", time.time()))
            seconds_held = int(time.time() - opened_ts)
            close_info = {
                "realized_pnl": pl,
                "realized_r": r,
                "bars_held": int(seconds_held / max(COOLDOWN_SEC, 1)),
                "seconds_held": seconds_held,
                "pnl_path": [pl],
                "spread_scores": [float(spread_cache.get(instr, 0.0) or 0.0)],
                "vol_scores": [float(plan.get("risk_diag", {}).get("regime_mult", 1.0))],
                "exit_at_structure": False,
                "exit_at_profile": False,
                "due_to_time_stop": False,
                "due_to_trailing": False,
                "due_to_execution_dislocation": False,
            }
            market_ctx = {
                "spread_bps": float(spread_cache.get(instr, 0.0) or 0.0) * 10000.0,
                "distance_struct_bps": 8.0,
                "distance_profile_bps": 8.0,
                "adverse_selection_score": 0.0,
                "move_spent_fraction": 0.4,
                "event_state": "blocked" if event_guardrails(instr) else "normal",
                "execution_regime": "normal",
                "regime_mismatch": False,
                "structure_context": "na",
                "profile_context": "na",
                "trigger_family": "runtime",
            }
            trade_intel_pipeline.on_trade_close({"trade_id": intel_tid}, close_info, market_ctx)

        s = strategy_stats[strat]
        s["n"] += 1
        if pl > 0:
            s["wins"] += 1
        s["sum_r"] += r
        s["last50"].append(r)
        strategy_perf[strat].append(r)
        daily_trade_budget["trades_closed_today"] = daily_trade_budget.get("trades_closed_today", 0) + 1
        if pl <= 0:
            daily_trade_budget["consecutive_losses"] = daily_trade_budget.get("consecutive_losses", 0) + 1
        else:
            daily_trade_budget["consecutive_losses"] = 0
        sess = session_label()
        update_bandit_reward(sess, strategy_impl_to_code(strat), r)

        if len(s["last50"]) >= RISK_CUTOFF_EXPECTANCY_TRADES and float(np.mean(s["last50"])) < 0:
            strategy_disable_until[strat] = time.time() + STRAT_DISABLE_COOLDOWN_MIN * 60
            log_event("RISK", instr, f"Disabled strategy {strat} for cooldown", {"mean_r": float(np.mean(s['last50']))}, level=1)
        last_tx_seen = tid

def edge_report(instr, score, regime, ev_guard, spr_info, beta_alpha, var_est, risk_mult, atrp):
    macro = fetch_macro_context() or {}
    return {
        "instr": instr,
        "score": round(float(score),3),
        "regime": regime,
        "spread_guard": spr_info,
        "beta_alpha": beta_alpha,
        "atr_pct": round(float(atrp),5),
        "event_window": ev_guard,
        "VaR99_param": round(float(var_est.get("param",0.0)),5),
        "DXY_bias": (macro.get("DXY_proxy") or {}).get("bias","unavailable"),
        "risk_mult": risk_mult
    }

def build_context_blob():
    global context_blob
    macro = fetch_macro_context()
    econ  = fetch_econ_calendar()
    sent  = fetch_trends_sentiment()
    corr  = correlation_matrix()
    
    # NEW: Get Forex Factory news
    news_events = fetch_forex_factory_events()
    
    regimes = {}
    skews = {}
    for ins in INSTRUMENTS:
        df = get_candles(ins, count=120)
        reg, mult = compute_intraday_regime(df) if df is not None else ("neutral",1.0)
        regimes[ins] = {"regime": reg, "mult": mult}
        skews[ins] = fetch_positioning(ins)
    
    context_blob = {
        "ts": utc_now_iso(),
        "session": current_session_info(),
        "macro": macro,
        "events": econ[:3] if isinstance(econ, list) else econ,
        "forex_factory_news": news_events[:5],  # NEW: Add top 5 news events
        "sentiment": sent,
        "correlations": corr,
        "regime": regimes,
        "risk": {"target_vol": TARGET_ANNUAL_VOL},
        "positioning": skews
    }

# ========= COSTS, RISK, ORDERS =========

def estimate_costs(instr):
    spr = spread_cache.get(instr, 0.0)
    px  = price_cache.get(instr, None)
    if not px or spr<=0: 
        return 0.0
    return spr

def edge_vs_cost(score, atr_val, price, instr):
    atr_frac = (atr_val / (price + 1e-9))
    exp_move = abs(score) * atr_frac
    costs = estimate_costs(instr) / (price + 1e-9)
    return exp_move / (costs + 1e-12)

def get_nav():
    acct = get_account_summary()
    return float(acct.get("NAV", 0.0)), acct.get("currency","USD")

def units_from_risk(instr, price, atr_val, direction, df=None, confidence=0.5, session_mult=1.0):
    nav,_ = get_nav()
    risk_dollars = nav * ACCOUNT_RISK_PCT
    stop_dist_price = 1.6 * atr_val
    if stop_dist_price <= 0 or price <= 0:
        return 0

    inst_vol = instrument_annualized_vol(df)
    risk_parity_scale = TARGET_ANNUAL_VOL / max(inst_vol, 1e-9)
    confidence_mult = max(0.8, min(1.2, 0.8 + confidence * 0.4))
    dollars = risk_dollars * risk_parity_scale * confidence_mult * max(0.25, session_mult)

    units = dollars / stop_dist_price
    notional = abs(units * price)
    max_notional = nav * MAX_LEVERAGE
    if notional > max_notional:
        units = max_notional / (price + 1e-9)
    return int(math.copysign(max(1, int(units)), 1 if direction>0 else -1))

def tp_sl_levels(instr, price, atr_val, direction, score, fat_tail_level):
    tail_boost = 0.3 if fat_tail_level>0.2 else 0.0
    mu_rn, rd, rf = fx_forward_drift(instr)
    carry_nudge = 0.4 if (direction>0 and mu_rn>0) or (direction<0 and mu_rn<0) else 0.0
    k_sl = 1.6 + tail_boost
    k_tp = 2.2 + (0.6 if abs(score)>0.6 else 0.0) + tail_boost/2.0 + carry_nudge
    sl = price - k_sl*atr_val if direction>0 else price + k_sl*atr_val
    tp = price + k_tp*atr_val if direction>0 else price - k_tp*atr_val
    return _round_price(instr, tp), _round_price(instr, sl)

def place_market_order(instr, units, tp=None, sl=None):
    order = {
        "order": {
            "units": str(units),
            "instrument": instr,
            "timeInForce": "FOK",
            "type": "MARKET",
            "positionFill": "DEFAULT"
        }
    }
    if tp is not None:
        order["order"]["takeProfitOnFill"] = {"price": f"{tp}"}
    if sl is not None:
        order["order"]["stopLossOnFill"] = {"price": f"{sl}"}
    return safe_post(f"{HOST}/accounts/{OANDA_ACCOUNTID}/orders", json_data=order)

def get_pending_orders():
    data = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/pendingOrders")
    return data.get("orders", []) if data else []

def cancel_order(order_id):
    try:
        r = session.put(f"{HOST}/accounts/{OANDA_ACCOUNTID}/orders/{order_id}/cancel", json={}, timeout=30)
        return r.ok
    except Exception:
        return False

def count_open_positions(instr): 
    return len(get_open_trades(instr))

def portfolio_var(price_map, horizon_days=1, cl=0.99):
    series = []
    for ins in INSTRUMENTS:
        df = get_candles(ins, count=200)
        if df is None: 
            continue
        r = np.log(df["c"]/df["c"].shift(1)).dropna()
        if len(r)>10: 
            series.append(r)
    if not series: 
        return {"param": 0.0}
    R = pd.concat(series, axis=1).mean(axis=1).dropna()
    mu, sig = float(R.mean()), float(R.std(ddof=1))
    z = 2.33  # 99%
    param = -(mu*horizon_days + sig*math.sqrt(horizon_days)*z)
    return {"param": param}

def strategy_sharpe():
    if len(trade_pnl_history)<30: 
        return 0.0
    arr = np.array(trade_pnl_history, dtype=float)
    mu = arr.mean(); sig = arr.std(ddof=1)
    if sig==0: 
        return 0.0
    ann = (mu/sig)*math.sqrt(12*24*252)
    return float(ann)

# ========= OPTION PRICING (Garman–Kohlhagen, Black–76) =========

def _norm_cdf(x): 
    return 0.5*(1+math.erf(x/math.sqrt(2)))

def _norm_pdf(x): 
    return (1/math.sqrt(2*math.pi))*math.exp(-0.5*x*x)

def garman_kohlhagen(S, K, T, sigma, rd, rf, call=True):
    if T<=0 or sigma<=0 or S<=0 or K<=0: 
        return {"price":0,"delta":0,"gamma":0,"vega":0,"theta":0}
    d1 = (math.log(S/K) + (rd - rf + 0.5*sigma*sigma)*T) / (sigma*math.sqrt(T))
    d2 = d1 - sigma*math.sqrt(T)
    if call:
        price = S*math.exp(-rf*T)*_norm_cdf(d1) - K*math.exp(-rd*T)*_norm_cdf(d2)
        delta = math.exp(-rf*T)*_norm_cdf(d1)
    else:
        price = K*math.exp(-rd*T)*_norm_cdf(-d2) - S*math.exp(-rf*T)*_norm_cdf(-d1)
        delta = -math.exp(-rf*T)*_norm_cdf(-d1)
    gamma = math.exp(-rf*T)*_norm_pdf(d1)/(S*sigma*math.sqrt(T))
    vega  = S*math.exp(-rf*T)*_norm_pdf(d1)*math.sqrt(T)
    theta = - (S*math.exp(-rf*T)*_norm_pdf(d1)*sigma)/(2*math.sqrt(T)) \
            - rd*K*math.exp(-rd*T)*(_norm_cdf(d2) if call else _norm_cdf(-d2)) \
            + rf*S*math.exp(-rf*T)*(_norm_cdf(d1) if call else _norm_cdf(-d1))
    return {"price":price, "delta":delta, "gamma":gamma, "vega":vega, "theta":theta, "d1":d1, "d2":d2}

def black76(F, K, T, sigma, r, call=True):
    if T<=0 or sigma<=0 or F<=0 or K<=0: 
        return {"price":0,"deltaF":0,"vega":0}
    d1 = (math.log(F/K) + 0.5*sigma*sigma*T)/(sigma*math.sqrt(T))
    d2 = d1 - sigma*math.sqrt(T)
    if call:
        price = math.exp(-r*T)*(F*_norm_cdf(d1) - K*_norm_cdf(d2))
        deltaF = math.exp(-r*T)*_norm_cdf(d1)
    else:
        price = math.exp(-r*T)*(K*_norm_cdf(-d2) - F*_norm_cdf(-d1))
        deltaF = -math.exp(-r*T)*_norm_cdf(-d1)
    vega = math.exp(-r*T)*F*_norm_pdf(d1)*math.sqrt(T)
    return {"price":price, "deltaF":deltaF, "vega":vega, "d1":d1, "d2":d2}

# ========= ADVANCED RISK & ANALYTICS =========

def kelly_criterion(win_rate: float, win_loss_ratio: float) -> float:
    """
    Kelly Criterion position sizing fraction.
    win_rate: probability of a win (0–1)
    win_loss_ratio: avg win / avg loss
    """
    try:
        k = win_rate - (1 - win_rate) / win_loss_ratio
        return max(0.0, min(k, 1.0))
    except ZeroDivisionError:
        return 0.0

def cvar(pnl_series: pd.Series, alpha: float = 0.975) -> float:
    """
    Conditional Value at Risk (Expected Shortfall)
    """
    if len(pnl_series) < 5:
        return np.nan
    var = np.quantile(pnl_series, 1 - alpha)
    es = pnl_series[pnl_series <= var].mean()
    return float(es)

def monte_carlo_var(pnl_series: pd.Series, alpha: float = 0.99, sims: int = 2000) -> float:
    """
    Monte Carlo VaR using bootstrap resampling.
    """
    if len(pnl_series) < 5:
        return np.nan
    sample_means = [np.mean(np.random.choice(pnl_series, len(pnl_series), replace=True))
                    for _ in range(sims)]
    return float(np.quantile(sample_means, 1 - alpha))

def sortino_ratio(returns: pd.Series, rf: float = 0.0) -> float:
    """
    Sortino ratio = (mean - rf) / downside deviation
    """
    if len(returns) < 5:
        return np.nan
    downside = returns[returns < rf]
    if downside.empty:
        return np.nan
    return float((returns.mean() - rf) / (np.std(downside, ddof=1) + 1e-9))

def omega_ratio(returns: pd.Series, threshold: float = 0.0) -> float:
    """
    Omega ratio = Prob(R>threshold) / Prob(R<threshold)
    """
    if len(returns) < 5:
        return np.nan
    gains = (returns > threshold).sum()
    losses = (returns < threshold).sum()
    return float(gains / (losses + 1e-9))

def tail_ratio(returns: pd.Series) -> float:
    """
    Tail ratio = 95th percentile / |5th percentile|
    """
    if len(returns) < 5:
        return np.nan
    return float(np.percentile(returns, 95) / abs(np.percentile(returns, 5)))

def max_drawdown(equity_curve: pd.Series) -> float:
    """
    Max drawdown in equity curve (%)
    """
    if len(equity_curve) < 5:
        return np.nan
    roll_max = np.maximum.accumulate(equity_curve)
    dd = equity_curve / roll_max - 1.0
    return float(dd.min())

def fetch_pnl_series(n: int = 100) -> pd.Series:
    """
    Fetch recent realized PnLs for risk analytics.
    """
    tx = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/transactions") or {}
    fills = [t for t in tx.get("transactions", []) if t.get("type") == "ORDER_FILL"]
    pnl = []
    for t in fills[-n:]:
        try:
            pnl.append(float(t.get("pl", 0.0)))
        except:
            pass
    return pd.Series(pnl) if pnl else pd.Series(dtype=float)

# ========= ADAPTIVE INTELLIGENCE CORE =========

ml_model = None
scaler = None
ml_last_train = 0
ML_FEATURE_NAMES = [
    "ret",
    "atrp",
    "vol5",
    "vol30",
    "regime_trend",
    "zscore20",
    "mom3",
    "mom10",
    "ema_spread",
    "rsi14",
]

def extract_features(df):
    """Builds ML-ready feature set from candle DataFrame."""
    df = df.copy()
    df["ret"] = np.log(df["c"] / df["c"].shift(1))
    df["atrp"] = atr(df, ATR_PERIOD) / (df["c"] + 1e-9)
    df["vol5"] = df["ret"].rolling(5).std(ddof=1)
    df["vol30"] = df["ret"].rolling(30).std(ddof=1)
    df["regime_trend"] = np.where(df["c"] > df["c"].rolling(20).mean(), 1, 0)
    df["zscore20"] = (df["c"] - df["c"].rolling(20).mean()) / (df["c"].rolling(20).std(ddof=1) + 1e-9)
    df["mom3"] = df["c"].pct_change(3)
    df["mom10"] = df["c"].pct_change(10)
    df["ema_spread"] = (ema(df["c"], 10) - ema(df["c"], 30)) / (df["c"] + 1e-9)
    df["rsi14"] = rsi(df["c"], 14) / 100.0
    df["target"] = np.where(df["ret"].shift(-1) > 0, 1, 0)
    df.dropna(inplace=True)
    X = df[ML_FEATURE_NAMES]
    y = df["target"].astype(int).values
    return X.values, y

def train_ml_model(instr="EUR_USD", window=500):
    """Retrains stacked classification models from latest candles."""
    global ml_model, ml_last_train
    df = get_candles(instr, count=window)
    if df is None or len(df) < 60:
        return None
    X, y = extract_features(df)
    if len(X) < 80:
        return None

    lr_model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=200))
    ])
    gb_model = GradientBoostingRegressor(
        n_estimators=120,
        learning_rate=0.05,
        max_depth=2,
        random_state=42,
    )

    lr_model.fit(X, y)
    gb_model.fit(X, y)

    ml_model = {
        "lr": lr_model,
        "gb": gb_model,
    }
    ml_last_train = time.time()
    logging.info(f"[ML] Ensemble trained on {instr} ({len(X)} samples, {len(ML_FEATURE_NAMES)} features)")
    return ml_model

def predict_pwin(instr):
    """Predicts probability of next-candle win using ML model."""
    global ml_model
    if ml_model is None:
        return None
    df = get_candles(instr, count=60)
    if df is None or len(df) < 30:
        return None
    X, _ = extract_features(df.tail(30))
    if len(X) == 0:
        return None
    x_last = X[-1].reshape(1, -1)

    if isinstance(ml_model, dict):
        p_lr = float(ml_model["lr"].predict_proba(x_last)[0][1])
        p_gb = float(np.clip(ml_model["gb"].predict(x_last)[0], 0.0, 1.0))
        return 0.6 * p_lr + 0.4 * p_gb

    p = ml_model.predict_proba(x_last)[0][1]
    return float(p)

def dynamic_position_size(score, volatility, base_risk):
    """Adaptive position sizing using confidence and volatility."""
    vol_adj = max(0.2, min(2.0, 0.6 / (volatility + 1e-9)))
    size = base_risk * abs(score) * vol_adj
    return np.clip(size, 0.2 * base_risk, 2.0 * base_risk)

def auto_calibrate_thresholds(pnl_series: pd.Series):
    """Auto-tunes Sharpe & Edge thresholds based on rolling hit-rate."""
    global MIN_EDGE_MULT_COST, SHARPE_FLOOR
    if len(pnl_series) < 50:
        return
    hit = (pnl_series > 0).mean()
    sharpe_est = (pnl_series.mean() / (pnl_series.std(ddof=1) + 1e-9)) * np.sqrt(252)
    if hit < 0.45:
        MIN_EDGE_MULT_COST = min(5.0, MIN_EDGE_MULT_COST + 0.2)
        SHARPE_FLOOR = max(0.5, SHARPE_FLOOR + 0.1)
    elif hit > 0.6:
        MIN_EDGE_MULT_COST = max(1.0, MIN_EDGE_MULT_COST - 0.1)
        SHARPE_FLOOR = max(0.3, SHARPE_FLOOR - 0.1)
    logging.info(f"[AUTO-TUNE] hit={hit:.2f}, Sharpe≈{sharpe_est:.2f}, "
                 f"new edge_min={MIN_EDGE_MULT_COST:.2f}, Sharpe_floor={SHARPE_FLOOR:.2f}")

# ========= QUANT RESEARCH & REGIME INTELLIGENCE =========
from statsmodels.tsa.stattools import adfuller
from scipy.signal import periodogram

def garch_lite_vol(df, window=100):
    """Estimate volatility clustering using ARCH(1) approximation."""
    df = df.copy()
    df["ret"] = np.log(df["c"] / df["c"].shift(1))
    df.dropna(inplace=True)
    if len(df) < 30:
        return np.nan
    mean_ret = df["ret"].mean()
    resid = df["ret"] - mean_ret
    var_t = resid ** 2
    alpha0 = var_t.mean() * 0.1
    alpha1 = min(0.9, np.corrcoef(var_t[:-1], var_t[1:])[0,1])
    forecast_var = alpha0 + alpha1 * var_t.iloc[-1]
    return float(np.sqrt(forecast_var))

def fourier_seasonality_scan(df, max_k=8):
    """Fourier transform of returns to find dominant periodicity."""
    df = df.copy()
    df["ret"] = np.log(df["c"] / df["c"].shift(1))
    df.dropna(inplace=True)
    if len(df) < 50:
        return None
    f, Pxx = periodogram(df["ret"])
    top_idx = np.argsort(Pxx)[-max_k:]
    periods = [int(1/f[i]) for i in top_idx if f[i] != 0]
    return sorted(periods)

def cointegration_test(series1, series2):
    """Engle-Granger cointegration test (ADF on residuals)."""
    if len(series1) != len(series2) or len(series1) < 50:
        return None
    X = np.vstack([series1, np.ones(len(series1))]).T
    beta = np.linalg.lstsq(X, series2, rcond=None)[0][0]
    resid = series2 - beta * series1
    adf_pval = adfuller(resid)[1]
    return {"beta": beta, "pval": adf_pval, "cointegrated": adf_pval < 0.05}

def detect_regime(df, vol_threshold=0.0015):
    """Classify regime: trending vs mean-reverting based on rolling std and momentum."""
    df = df.copy()
    df["ret"] = np.log(df["c"] / df["c"].shift(1))
    df["vol"] = df["ret"].rolling(30).std()
    df["mom"] = df["c"] / df["c"].shift(10) - 1
    df.dropna(inplace=True)
    if len(df) < 50:
        return "unknown"
    vol_state = "high-vol" if df["vol"].iloc[-1] > vol_threshold else "low-vol"
    trend_state = "trending" if abs(df["mom"].iloc[-1]) > 0.003 else "mean-revert"
    return f"{vol_state}/{trend_state}"

# ========= COMPRESSION / BREAKOUT ALPHA =========
def bollinger_bandwidth(series: pd.Series, n: int = 20):
    """BB bandwidth = (upper - lower) / mid; smaller = tighter squeeze."""
    ma = series.rolling(n).mean()
    sd = series.rolling(n).std(ddof=1)
    upper = ma + 2*sd
    lower = ma - 2*sd
    mid = ma
    width = (upper - lower) / (mid.abs() + 1e-9)
    return width

def donchian_channels(df: pd.DataFrame, n: int = 40):
    """Returns (upper, lower) Donchian lines over close prices."""
    hi = df["h"].rolling(n).max()
    lo = df["l"].rolling(n).min()
    return hi, lo

# ==== Liquidity Swings (Lux-style) params ====
LIQ_SW_LENGTH       = int(os.environ.get("LIQ_SW_LENGTH", "14"))   # pivot lookback
LIQ_SW_AREA         = os.environ.get("LIQ_SW_AREA", "wick")        # 'wick' or 'full'
LIQ_SW_FILTER       = os.environ.get("LIQ_SW_FILTER", "count")     # 'count' or 'volume'
LIQ_SW_THRESHOLD    = float(os.environ.get("LIQ_SW_THRESHOLD", "0"))
LIQ_SW_LOOKAHEAD_MAX= int(os.environ.get("LIQ_SW_LOOKAHEAD_MAX", "400"))  # how many bars after pivot to tally


def compression_score(px: pd.Series, n:int=BBANDS_N, q:float=0.20):
    """0..1 score: 1 = extreme compression. Based on rolling BB width vs its own history quantiles."""
    bw = bollinger_bandwidth(px, n).dropna()
    if len(bw) < n+5:
        return 0.0, None
    recent = bw.iloc[-1]
    hist = bw.tail(200)          # robust window
    lo = np.nanquantile(hist, q)
    hi = np.nanquantile(hist, 1-q)
    if hi <= lo:
        return 0.0, float(recent)
    # map bandwidth to [0,1] where low width -> high score
    s = float(np.clip((hi - recent) / (hi - lo), 0, 1))
    return s, float(recent)

def breakout_signal(df: pd.DataFrame, n:int=DONCHIAN_N):
    """
    +1 if price breaks above upper Donchian (bullish breakout)
    -1 if price breaks below lower Donchian (bearish breakout)
     0 otherwise. Also return level and magnitude.
    """
    if df is None or len(df) < n+2:
        return 0, None, 0.0
    upper, lower = donchian_channels(df, n)
    px = df["c"].iloc[-1]
    up = float(upper.iloc[-2])  # yesterday's band to avoid lookahead
    lo = float(lower.iloc[-2])
    # magnitude: normalized distance from band
    mag_up = (px - up) / (df["c"].rolling(50).std(ddof=0).iloc[-1] + 1e-9)
    mag_lo = (lo - px) / (df["c"].rolling(50).std(ddof=0).iloc[-1] + 1e-9)
    if px > up:
        return +1, up, float(np.tanh(mag_up/2))
    if px < lo:
        return -1, lo, float(np.tanh(mag_lo/2))
    return 0, None, 0.0

def choose_order_for_breakout(instr:str, df:pd.DataFrame, score:float):
    """
    If we are in strong compression and price is near a Donchian trigger,
    prefer a STOP entry at the breakout level to reduce false starts.
    Returns dict:
      {"use_stop": bool, "stop_price": float|None, "dir": +1/-1/0,
       "comp_score": float, "brk_mag": float}
    """
    comp_s, _bw = compression_score(df["c"])
    dirn, level, brk_mag = breakout_signal(df)
    # Heuristic gate: only consider STOP if compression strong or breakout magnitude decent
    use_stop = (comp_s >= MIN_COMPRESSION_SCORE) or (abs(brk_mag) >= 0.6)
    # Require direction aligned with your ensemble score
    if score*dirn <= 0:
        use_stop = False
        level = None
    return {
        "use_stop": bool(use_stop and level is not None),
        "stop_price": float(level) if (use_stop and level is not None) else None,
        "dir": int(dirn),
        "comp_score": float(comp_s),
        "brk_mag": float(brk_mag)
    }

def place_stop_entry_order(instr, units, price, tp=None, sl=None):
    """
    OANDA stop entry: triggers a MARKET when price crosses 'price'.
    For long, 'price' above current; for short, below current.
    """
    order = {
        "order": {
            "type": "STOP",
            "instrument": instr,
            "units": str(units),
            "price": f"{_round_price(instr, price)}",
            "timeInForce": "GTC",
            "positionFill": "DEFAULT"
        }
    }
    if tp is not None:
        order["order"]["takeProfitOnFill"] = {"price": f"{tp}"}
    if sl is not None:
        order["order"]["stopLossOnFill"] = {"price": f"{sl}"}
    return safe_post(f"{HOST}/accounts/{OANDA_ACCOUNTID}/orders", json_data=order)

# ========= LIQUIDITY SWINGS (LuxAlgo-inspired) =========
# Higher number = stronger draw on liquidity (above vs below)

def _pivot_indices(px: pd.Series, length: int):
    """Return lists of pivot-high and pivot-low bar indices (like ta.pivothigh/low with symmetric length)."""
    # we use close as Pine uses generic series — for high/low areas we still reference h/l on that pivot bar
    hi_idx, lo_idx = [], []
    vals = px.values
    L = length
    for i in range(L, len(px)-L):
        window = vals[i-L:i+L+1]
        center = vals[i]
        if center == window.max() and np.argmax(window) == L:
            hi_idx.append(px.index[i])
        if center == window.min() and np.argmin(window) == L:
            lo_idx.append(px.index[i])
    return hi_idx, lo_idx

def _area_bounds_at_pivot(df: pd.DataFrame, idx, area_mode: str):
    """Return (top, bottom) of the swing area at the pivot bar."""
    i = df.index.get_loc(idx)
    h = float(df["h"].iloc[i]); l = float(df["l"].iloc[i])
    o = float(df["o"].iloc[i]); c = float(df["c"].iloc[i])
    if area_mode == "full":
        return (h, l)
    # wick extremity (Lux's default): top at high, bottom at body extremity for highs; inverse for lows.
    # We’ll choose based on whether it’s closer to a swing high or low, caller decides which to use.
    # We provide both possible bottoms so caller can pick; but for simplicity we return:
    return (h, max(o, c)), (min(o, c), l)  # ((top, body-bottom-for-high), (body-top-for-low, bottom))

def _tally_crossings(df: pd.DataFrame, start_pos: int, top: float, btm: float, lookahead_max: int):
    """
    Count how many subsequent bars 'span' the level block (low < top and high > btm),
    and accumulate tick volume (OANDA volume).
    """
    cnt = 0
    vol = 0.0
    end = min(len(df), start_pos + lookahead_max + 1)
    for j in range(start_pos+1, end):
        if df["l"].iloc[j] < top and df["h"].iloc[j] > btm:
            cnt += 1
            vol += float(df["v"].iloc[j])
    return cnt, vol

def liquidity_swings(df: pd.DataFrame,
                     length: int = LIQ_SW_LENGTH,
                     area_mode: str = LIQ_SW_AREA,
                     filter_by: str = LIQ_SW_FILTER,
                     threshold: float = LIQ_SW_THRESHOLD,
                     lookahead_max: int = LIQ_SW_LOOKAHEAD_MAX):
    """
    Identify swing-high and swing-low 'blocks' and compute their post-creation interaction:
      - Count of future bars spanning the block
      - Sum of 'volume' (tick count) inside the block
    Build lists of candidate pools above/below current price with a 'target' (count or volume).
    """
    if df is None or len(df) < 2*length+5:
        return {"above": [], "below": [], "mid": float("nan"), "atr": 0.0}

    px = df["c"]
    hi_idx, lo_idx = _pivot_indices(px, length)
    mid = float(px.iloc[-1])

    # ATR for distance normalization
    atrv = float(atr(df, ATR_PERIOD).iloc[-1] or 1e-9)

    above, below = [], []

    # Process pivot highs → buy-side liquidity above current price
    for idx in hi_idx:
        i = df.index.get_loc(idx)
        if area_mode == "full":
            top, btm = _area_bounds_at_pivot(df, idx, "full")
        else:
            top, btm_high = _area_bounds_at_pivot(df, idx, "wick")
            # for highs, use (top = high, btm = body bottom)
            btm = btm_high[1] if isinstance(btm_high, tuple) else btm_high
        cnt, vol = _tally_crossings(df, i, top, btm, lookahead_max)
        target = cnt if filter_by == "count" else vol
        if target > threshold:
            item = {"price": float(top), "count": int(cnt), "volume": float(vol), "target": float(target), "top": float(top), "btm": float(btm)}
            if item["price"] > mid:
                above.append(item)

    # Process pivot lows → sell-side liquidity below current price
    for idx in lo_idx:
        i = df.index.get_loc(idx)
        if area_mode == "full":
            top, btm = _area_bounds_at_pivot(df, idx, "full")
        else:
            # for lows, from the wick function we want (body top, low)
            both = _area_bounds_at_pivot(df, idx, "wick")
            top, btm = both[1][0], both[1][1]
        cnt, vol = _tally_crossings(df, i, top, btm, lookahead_max)
        target = cnt if filter_by == "count" else vol
        if target > threshold:
            # we key on 'btm' as the level plotted for lows (like script’s line at pl_btm)
            item = {"price": float(btm), "count": int(cnt), "volume": float(vol), "target": float(target), "top": float(top), "btm": float(btm)}
            if item["price"] < mid:
                below.append(item)

    # choose nearest candidates (like “nearest zone”)
    above = sorted(above, key=lambda x: x["price"])
    below = sorted(below, key=lambda x: x["price"], reverse=True)

    return {"above": above, "below": below, "mid": mid, "atr": atrv}

def lux_draw_on_liquidity(df: pd.DataFrame,
                          length: int = LIQ_SW_LENGTH,
                          area_mode: str = LIQ_SW_AREA,
                          filter_by: str = LIQ_SW_FILTER,
                          threshold: float = LIQ_SW_THRESHOLD):
    """
    Compute a draw score similar to ‘Liquidity Swings’:
    For nearest above and nearest below pools, define:
      score_pool = target / (1 + distance_in_ATRs)
    draw = (score_above - score_below) / (score_above + score_below + eps) ∈ [-1..1]
    Also return raw sides so you can display them.
    """
    pools = liquidity_swings(df, length, area_mode, filter_by, threshold)
    if pools["atr"] <= 0 or (not pools["above"] and not pools["below"]):
        return {
            "lux_draw": 0.0,
            "lux_above_score": 0.0,
            "lux_below_score": 0.0,
            "lux_meta": pools,
        }

    mid = pools["mid"]; atrv = pools["atr"]; eps = 1e-9
    na = pools["above"][0] if pools["above"] else None
    nb = pools["below"][0] if pools["below"] else None

    def score(pool):
        if not pool: return 0.0
        dist_atr = abs(pool["price"] - mid) / (atrv + eps)
        # weight by chosen target; closer pool gets more pull
        return float(pool["target"] / (1.0 + dist_atr))

    sa = score(na)
    sb = score(nb)
    draw = (sa - sb) / (sa + sb + eps)
    return {
        "lux_draw": float(np.clip(draw, -1.0, 1.0)),  # higher ⇒ draw upward (buy-side), lower ⇒ draw downward
        "lux_above_score": float(sa),
        "lux_below_score": float(sb),
        "lux_meta": pools,
    }


# ========= FIBONACCI SYSTEM =========
# Add this whole block anywhere above the TRADING LOGIC section (e.g., after COMPRESSION / BREAKOUT)
# and then apply the small integration edits shown further below.

from dataclasses import dataclass

FIB_RETRACEMENTS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
FIB_EXTENSIONS   = [1.127, 1.272, 1.414, 1.618, 2.0]

@dataclass
class FibPack:
    swing_high: float
    swing_low: float
    direction: int        # +1 uptrend leg, -1 downtrend leg
    retracements: dict    # level_name -> price
    extensions: dict      # level_name -> price


def _zigzag_swings(px: pd.Series, pct: float = 0.8) -> tuple[float, float, int]:
    """
    Lightweight zigzag to find most recent impulse leg.
    pct: threshold (in ATR multiples if available) – here as % of price move in per‑mille.
    Returns (swing_high, swing_low, direction)
    """
    if len(px) < 30:
        return float(px.iloc[-1]), float(px.iloc[-1]), 0
    # use ATR to scale threshold if available
    df_tmp = pd.DataFrame({"c": px})
    atrv = atr(df_tmp.assign(h=px.rolling(2).max(), l=px.rolling(2).min()), ATR_PERIOD).iloc[-1]
    thr = max(atrv * 1.2, px.iloc[-1] * (pct / 100.0 / 10.0))  # ~0.08% default, or 1.2*ATR

    hi = float(px.iloc[-1])
    lo = float(px.iloc[-1])
    mode = 0  # 0 unknown, +1 rising, -1 falling
    for v in px.iloc[::-1]:
        v = float(v)
        if mode >= 0:
            hi = max(hi, v)
            if hi - v > thr:
                # reversal down detected
                lo = v
                mode = -1
                break
        if mode <= 0:
            lo = min(lo, v)
            if v - lo > thr:
                # reversal up detected
                hi = v
                mode = +1
                break
    # if we broke on down leg, last impulse was up (low -> high)
    if mode == -1:
        swing_low = lo
        swing_high = hi
        direction = +1
    elif mode == +1:
        swing_low = lo
        swing_high = hi
        direction = -1
    else:
        swing_low = float(px.min())
        swing_high = float(px.max())
        direction = 1 if px.iloc[-1] >= px.iloc[0] else -1
    return swing_high, swing_low, direction


def build_fib_levels(px: pd.Series) -> FibPack | None:
    if px is None or len(px) < 20:
        return None
    hi, lo, direction = _zigzag_swings(px)
    if hi == lo:
        return None
    leg = hi - lo
    if direction > 0:  # up leg: retrace levels measured downward from high
        rets = {f"{int(r*100)}%": hi - r * leg for r in FIB_RETRACEMENTS}
        exts = {f"{int(e*100)}%": hi + (e - 1.0) * leg for e in FIB_EXTENSIONS}
    else:              # down leg: retrace levels measured upward from low
        rets = {f"{int(r*100)}%": lo + r * leg for r in FIB_RETRACEMENTS}
        exts = {f"{int(e*100)}%": lo - (e - 1.0) * leg for e in FIB_EXTENSIONS}
    return FibPack(swing_high=float(hi), swing_low=float(lo), direction=int(direction),
                   retracements=rets, extensions=exts)


def _nearest_level(price: float, levels: dict[str, float]) -> tuple[str, float, float]:
    best_key, best_px, best_dist = None, None, 1e9
    for k, v in levels.items():
        d = abs(price - float(v))
        if d < best_dist:
            best_key, best_px, best_dist = k, float(v), d
    return best_key or "", best_px or price, float(best_dist)


def fib_confluence_score(df: pd.DataFrame, fib: FibPack) -> dict:
    """Score confluence around price using distance to fib levels, Donchian, EMA20 and order book."""
    price = float(df["c"].iloc[-1])
    ema_mid = ema(df["c"], EMA_PERIOD).iloc[-1]
    upper, lower = donchian_channels(df, DONCHIAN_N)
    don_up, don_lo = float(upper.iloc[-1]), float(lower.iloc[-1])

    # nearest retrace + extension
    r_key, r_px, r_dist = _nearest_level(price, fib.retracements)
    e_key, e_px, e_dist = _nearest_level(price, fib.extensions)

    # normalize distances by ATR
    atr_val = float(atr(df, ATR_PERIOD).iloc[-1] or 1e-9)
    nd_r = min(3.0, r_dist / (atr_val + 1e-9))
    nd_e = min(3.0, e_dist / (atr_val + 1e-9))

    # proximity scores (closer is better)
    r_score = 1.0 - nd_r / 3.0
    e_score = 1.0 - nd_e / 3.0

    # Donchian & EMA alignment
    ema_near = 1.0 - min(3.0, abs(price - ema_mid) / (atr_val + 1e-9)) / 3.0
    don_near = max(
        1.0 - min(3.0, abs(price - don_up) / (atr_val + 1e-9)) / 3.0,
        1.0 - min(3.0, abs(price - don_lo) / (atr_val + 1e-9)) / 3.0,
    )

    # compression bonus
    comp_s, _bw = compression_score(df["c"], n=BBANDS_N, q=SQUEEZE_Q)

    # aggregate confluence
    confl = 0.35 * r_score + 0.15 * e_score + 0.25 * ema_near + 0.25 * don_near
    confl = float(np.clip(confl, 0.0, 1.0))

    return {
        "price": price,
        "nearest_retrace": {"key": r_key, "px": r_px, "z_atr": r_dist / (atr_val + 1e-9)},
        "nearest_ext": {"key": e_key, "px": e_px, "z_atr": e_dist / (atr_val + 1e-9)},
        "ema_near": float(ema_near),
        "don_near": float(don_near),
        "compression": float(comp_s),
        "confluence": confl,
    }


def fib_signals(df: pd.DataFrame) -> dict:
    """Return compact signal suite from fib logic for integration into ensemble."""
    fib = build_fib_levels(df["c"]) if df is not None else None
    if fib is None:
        return {"fib_confluence": 0.0, "fib_retrace_bias": 0.0, "fib_ext_bias": 0.0}
    info = fib_confluence_score(df, fib)

    # Bias rules:
    #  - In up leg: prefer buys on 50–61.8% retrace; target 127–161.8% ext
    #  - In down leg: symmetric
    r_key = info["nearest_retrace"]["key"]
    dirn = fib.direction
    retrace_buy_zone = r_key in ("50%", "61%", "62%", "61.8%", "618%", "50")  # tolerate variants
    retrace_sell_zone = retrace_buy_zone

    retrace_bias = 0.0
    if dirn > 0 and retrace_buy_zone:
        retrace_bias = +1.0
    elif dirn < 0 and retrace_sell_zone:
        retrace_bias = -1.0

    # extension bias is weaker (used for TP targeting), but we map to signal as mild momentum
    ext_bias = +0.25 if dirn > 0 else -0.25

    return {
        "fib_confluence": float(info["confluence"]),
        "fib_retrace_bias": float(retrace_bias * info["confluence"]),
        "fib_ext_bias": float(ext_bias),
        "_fib_meta": {"pack": fib, "info": info},  # for consumers that want detailed levels
    }


def fib_trade_plan(instr: str, df: pd.DataFrame, score_hint: float = 0.0) -> dict | None:
    """Build an executable plan using fib confluence. Returns dict with sizing and levels; does NOT place orders."""
    if df is None or len(df) < 60:
        return None
    fib = build_fib_levels(df["c"])  # FibPack
    if fib is None:
        return None
    info = fib_confluence_score(df, fib)
    price = float(df["c"].iloc[-1])
    atr_val = float(atr(df, ATR_PERIOD).iloc[-1] or 0.0)

    # default direction from fib leg, nudged by ensemble hint
    direction = fib.direction
    direction = 1 if score_hint > 0.15 else -1 if score_hint < -0.15 else direction

    # choose entry: 50–61.8 retrace if nearby; otherwise Donchian breakout in direction
    r_key, r_px, r_z = info["nearest_retrace"]["key"], info["nearest_retrace"]["px"], info["nearest_retrace"]["z_atr"]
    use_retrace = (r_key in ("50%", "61%", "61.8%", "50")) and (r_z <= 1.2)

    if use_retrace:
        entry = float(r_px)
        use_stop_order = False  # limit/market style entry at level vicinity
    else:
        # fallback to Donchian breakout
        up, lo = donchian_channels(df, DONCHIAN_N)
        lvl = float(up.iloc[-1]) if direction > 0 else float(lo.iloc[-1])
        entry = lvl
        use_stop_order = True

    # stops/targets around fib structure
    if direction > 0:
        sl = min(float(fib.retracements.get("78%", entry - 1.6 * atr_val)), entry - 1.6 * atr_val)
        tp1 = float(next((fib.extensions[k] for k in ("127%", "161%", "161.8%") if k in fib.extensions), entry + 2.2 * atr_val))
    else:
        sl = max(float(fib.retracements.get("78%", entry + 1.6 * atr_val)), entry + 1.6 * atr_val)
        tp1 = float(next((fib.extensions[k] for k in ("127%", "161%", "161.8%") if k in fib.extensions), entry - 2.2 * atr_val))

    # position size from existing risk model
    units = units_from_risk(instr, price, atr_val, direction)

    return {
        "instr": instr,
        "dir": "BUY" if direction > 0 else "SELL",
        "direction": int(direction),
        "entry": float(entry),
        "stop_loss": float(_round_price(instr, sl)),
        "take_profit": float(_round_price(instr, tp1)),
        "atr": float(atr_val),
        "use_stop_order": bool(use_stop_order),
        "units": int(units),
        "fib": {
            "swing_high": fib.swing_high,
            "swing_low": fib.swing_low,
            "retracements": fib.retracements,
            "extensions": fib.extensions,
        },
        "confluence": info,
    }



# ========= TP/SL HOOK (optional) =========
# If you want TP/SL to prefer fib targets automatically, replace tp_sl_levels() with this variant:

def tp_sl_levels_fib_first(instr, price, atr_val, direction, score, fat_tail_level, df=None):
    tail_boost = 0.3 if fat_tail_level > 0.2 else 0.0
    mu_rn, rd, rf = fx_forward_drift(instr)
    carry_nudge = 0.4 if (direction > 0 and mu_rn > 0) or (direction < 0 and mu_rn < 0) else 0.0

    tp_tp = None
    sl_sl = None
    if df is not None and len(df) >= 30:
        fib = build_fib_levels(df["c"]) or None
        if fib is not None:
            if direction > 0:
                # choose first available extension target
                for k in ("127%", "141%", "161%", "161.8%", "200%"):
                    if k in fib.extensions:
                        tp_tp = fib.extensions[k]
                        break
                # stop beyond 78.6 retrace or 1.6*ATR fallback
                sl_sl = min(fib.retracements.get("78%", price - 1.6 * atr_val), price - 1.6 * atr_val)
            else:
                for k in ("127%", "141%", "161%", "161.8%", "200%"):
                    if k in fib.extensions:
                        tp_tp = fib.extensions[k]
                        break
                sl_sl = max(fib.retracements.get("78%", price + 1.6 * atr_val), price + 1.6 * atr_val)

    # if fib not available, fall back to original scheme
    if tp_tp is None or sl_sl is None:
        k_sl = 1.6 + tail_boost
        k_tp = 2.2 + (0.6 if abs(score) > 0.6 else 0.0) + tail_boost / 2.0 + carry_nudge
        sl_sl = price - k_sl * atr_val if direction > 0 else price + k_sl * atr_val
        tp_tp = price + k_tp * atr_val if direction > 0 else price - k_tp * atr_val

    return _round_price(instr, tp_tp), _round_price(instr, sl_sl)

# ========= DISCORD COMMANDS =========
# Add these commands under the DISCORD BOT commands section.
@bot.command(name="luxliq")
async def luxliq_cmd(ctx, instrument: str, length: int = LIQ_SW_LENGTH):
    instr = instrument.upper()
    if instr not in INSTRUMENTS:
        await ctx.send(f"Unknown instrument. Choose from {', '.join(INSTRUMENTS)}")
        return
    df = get_candles(instr, count=max(300, length*20))
    if df is None:
        await ctx.send("unavailable")
        return
    lux = lux_draw_on_liquidity(df, length=length,
                                area_mode="full" if LIQ_SW_AREA.lower().startswith("full") else "wick",
                                filter_by="volume" if LIQ_SW_FILTER.lower().startswith("vol") else "count",
                                threshold=LIQ_SW_THRESHOLD)
    pools = lux["lux_meta"]
    na = pools["above"][0]["price"] if pools["above"] else None
    nb = pools["below"][0]["price"] if pools["below"] else None
    await ctx.send(
        f"{instr} lux_draw={lux['lux_draw']:+.2f} "
        f"| above_score={lux['lux_above_score']:.2f} (nearest_above={na}) "
        f"| below_score={lux['lux_below_score']:.2f} (nearest_below={nb})"
    )

@bot.command(name="fib")
async def fib_cmd(ctx, instrument: str, lookback: int = 240):
    instr = instrument.upper()
    if instr not in INSTRUMENTS:
        await ctx.send(f"Unknown instrument. Choose from {', '.join(INSTRUMENTS)}")
        return
    df = get_candles(instr, count=max(60, lookback))
    if df is None:
        await ctx.send("unavailable")
        return
    fib = build_fib_levels(df["c"])
    if fib is None:
        await ctx.send("not enough structure for fib levels")
        return
    info = fib_confluence_score(df, fib)
    lines = [
        f"**{instr} Fib** — leg: {'UP' if fib.direction>0 else 'DOWN'} | swing_hi={fib.swing_high:.5f} swing_lo={fib.swing_low:.5f}",
        "Retracements:" ,
    ]
    lines += [f" {k}: {v:.5f}" for k, v in fib.retracements.items()]
    lines += ["Extensions:"]
    lines += [f" {k}: {v:.5f}" for k, v in fib.extensions.items()]
    lines += [
        f"Confluence≈{info['confluence']:.2f} | near_retrace={info['nearest_retrace']['key']} ({info['nearest_retrace']['px']:.5f}) "
        f"| compression={info['compression']:.2f}"
    ]
    await ctx.send("\n".join(lines))

@bot.command(name="fibplan")
async def fibplan_cmd(ctx, instrument: str):
    instr = instrument.upper()
    if instr not in INSTRUMENTS:
        await ctx.send(f"Unknown instrument. Choose from {', '.join(INSTRUMENTS)}")
        return
    df = get_candles(instr, count=300)
    if df is None:
        await ctx.send("unavailable")
        return
    # use cached ensemble score if available as hint
    cached = signal_cache.get(instr, {}) if isinstance(signal_cache.get(instr), dict) else {}
    score_hint = float(cached.get("score", 0.0) or 0.0)
    plan = fib_trade_plan(instr, df, score_hint)
    if plan is None:
        await ctx.send("no plan")
        return
    lines = [
        f"**{instr} Fib Plan** dir={plan['dir']} units={plan['units']}",
        f"entry≈{plan['entry']:.5f} | tp={plan['take_profit']:.5f} | sl={plan['stop_loss']:.5f} | use_stop_order={plan['use_stop_order']}",
        f"confluence≈{plan['confluence']['confluence']:.2f} (compression={plan['confluence']['compression']:.2f})",
    ]
    await ctx.send("\n".join(lines))

# ========= TRADE LOOP HOOKS (integration points) =========
# 1) In trade_once(), after computing 'sigs' and before calling ensemble_score(...), add:
#       fibs = fib_signals(df)
#       sigs.update({k: v for k, v in fibs.items() if not k.startswith('_')})
#
# 2) Replace the call to 'ensemble_score(...)' with 'ensemble_score_with_fib(...)'.
#
# 3) When computing tp/sl, pass df to the fib‑aware version, e.g.:
#       tp, sl = tp_sl_levels_fib_first(instr, price, atr_val, direction, score, sigs.get("fat_tails", 0.0), df=df)
#
# 4) (Optional) In choose_order_for_breakout(), you may bias STOP usage if fib compression is strong:
#       comp_bonus = sigs.get('fib_confluence', 0.0)
#       use_stop = use_stop or comp_bonus >= 0.6



# ========= TRADING LOGIC =========

async def trade_once(instr, director_item=None, world_state=None):
    try:
        snapshot = build_market_snapshot(instr)
        if not snapshot:
            return

        session_info = current_session_info()
        session_name = session_info["session_name"]

        nav, _ = get_nav()
        kill, kill_diag = daily_kill_switch_triggered(nav)
        if kill:
            log_event("RISK", instr, "Daily kill switch active", kill_diag, level=1)
            return

        allowed_codes = (director_item or {}).get("strategies") or list(STRATEGY_CATALOG.keys())
        allowed_impl = [strategy_code_to_impl(c) for c in allowed_codes]
        plan, candidates = strategy_router(instr, snapshot, allowed_impl=allowed_impl)
        replay_log({"ts": utc_now_iso(), "type": "proposals", "instrument": instr, "director": director_item, "candidates": candidates, "selected": plan})

        if not plan:
            daily_trade_budget["missed_trades"] = daily_trade_budget.get("missed_trades", 0) + 1
            log_event("DECISION", instr, "No eligible trade plan", {"regime": snapshot["regime"]}, level=1)
            return

        prep_candidate = {
            "trade_id": plan_id(plan),
            "instrument": plan["instrument"],
            "strategy_name": plan["strategy"],
            "setup_type": plan["strategy"],
            "side": plan["side"],
            "entry_price": plan["entry_price"],
            "stop_loss": plan["stop_loss"],
            "take_profit": plan["take_profit"],
            "order_type": plan["order_type"],
            "confidence": plan.get("confidence", 0.5),
            "ev_r": plan.get("ev_r", 0.0),
            "rr": plan.get("rr", 0.0),
            "intel_quality_score": float(plan.get("confidence", 0.5)),
            "entry_precision_score": 0.5,
            "execution_feasibility_score": float(np.clip(1.0 - snapshot.get("spread_info", {}).get("percentile", 50.0) / 100.0, 0.0, 1.0)),
            "regime_alignment_score": 0.2 if snapshot.get("mode") == "high_vol" else 0.8,
        }
        prep_market = {
            "execution_risk_score": float(np.clip(snapshot.get("spread_info", {}).get("percentile", 50.0) / 100.0, 0.0, 1.0)),
            "event_risk": bool(snapshot.get("event_block", False)),
            "spread_expensive": bool(snapshot.get("spread_block", False)),
        }
        prep_portfolio = {
            "available_risk_score": float(np.clip(1.0 - current_portfolio_heat(nav) / max(PORTFOLIO_HEAT_LIMIT, 1e-9), 0.0, 1.0)),
        }
        prep_runtime = {
            "session_name": session_name,
            "regime_name": snapshot.get("regime", "unknown"),
            "spread_regime": "wide" if snapshot.get("spread_block") else "normal",
            "recent_performance": {
                "session_edge_score": 0.4 if daily_trade_budget.get("consecutive_losses", 0) >= 3 else 0.7,
                "recent_performance_score": 0.4 if daily_trade_budget.get("consecutive_losses", 0) >= 2 else 0.6,
            },
        }
        trade_prep = trade_intel_pipeline.prepare_trade(prep_candidate, prep_market, prep_portfolio, prep_runtime)
        if trade_prep.get("block_trade"):
            log_event("RISK", instr, "Trade intel blocked plan", {"reason_codes": trade_prep.get("reason_codes", [])}, level=1)
            return

        approved_plan, risk_diag = risk_approve_and_size(plan, snapshot, trade_prep=trade_prep)
        if not approved_plan:
            log_event("RISK", instr, "Plan blocked by portfolio risk", risk_diag, level=1)
            return
        approved_plan["trade_intel_id"] = trade_prep.get("trade_id")
        approved_plan["trade_intel_exit_plan"] = getattr(trade_prep.get("exit_plan"), "to_flat_dict", lambda: {})()

        pid = plan_id(approved_plan)
        if plan_seen_recently(pid):
            return

        resp, exec_diag = execute_trade_plan(approved_plan, snapshot)
        if resp is None:
            log_event("ORDER", instr, "Execution skipped", exec_diag, level=1)
            return

        trade_id = None
        if isinstance(resp, dict):
            fill = resp.get("orderFillTransaction") or {}
            trade_opened = (fill.get("tradeOpened") or {})
            trade_id = trade_opened.get("tradeID")
        if trade_id:
            daily_trade_budget["trades_opened_today"] = daily_trade_budget.get("trades_opened_today", 0) + 1
            daily_trade_budget["last_open_ts"] = time.time()
            trade_entry_meta[trade_id] = {
                "ts": time.time(),
                "strategy": approved_plan["strategy"],
                "score": approved_plan["ev_r"],
                "entry_type": approved_plan["order_type"],
                "be_moved": False,
                "partial_taken": False,
                "time_stop_bars": approved_plan.get("time_stop_bars", TIME_STOP_BARS),
                "trade_intel_id": approved_plan.get("trade_intel_id"),
                "trade_intel_exit_plan": approved_plan.get("trade_intel_exit_plan", {}),
            }
            if approved_plan.get("trade_intel_id"):
                trade_intel_pipeline.on_trade_open({"trade_id": approved_plan.get("trade_intel_id"), "entry_filled": float(fill.get("price", approved_plan.get("entry_price", 0.0)) or 0.0)}, {
                    "session_name": session_name,
                    "regime_name": snapshot.get("regime", "unknown"),
                })

        log_event("ORDER", instr, "Executed plan", {"strategy": approved_plan["strategy"], "type": approved_plan["order_type"], "units": approved_plan["units"], **exec_diag, **risk_diag, "session": session_name}, level=1)
        replay_log({"ts": utc_now_iso(), "type": "execution", "instrument": instr, "plan": approved_plan, "exec": exec_diag})

    except Exception as e:
        logger.exception(f"trade_once error {instr}: {e}")


def generate_eod_payload():
    strat_rows = {}
    aggregate_r = []
    for k, v in strategy_stats.items():
        n = int(v.get("n", 0))
        wins = int(v.get("wins", 0))
        last_r = [float(x) for x in list(v.get("last50", []))]
        aggregate_r.extend(last_r)
        avg_r = float(v.get("sum_r", 0.0) / max(1, n))
        r_std = float(np.std(last_r)) if len(last_r) >= 2 else 0.0
        profit_factor = 9.99
        pos_sum = sum(x for x in last_r if x > 0)
        neg_sum = abs(sum(x for x in last_r if x < 0))
        if neg_sum > 0:
            profit_factor = float(pos_sum / neg_sum)
        strat_rows[k] = {
            "trades": n,
            "win_rate": (wins / max(1, n)),
            "expectancy_r": avg_r,
            "stddev_r": r_std,
            "profit_factor": profit_factor,
            "sample_size": len(last_r),
        }
    skipped = []
    for e in list(get_log(400)):
        if e.get("kind") == "DECISION" and str(e.get("msg", "")).startswith("Skip"):
            skipped.append(e.get("msg"))

    total_closed = int(daily_trade_budget.get("trades_closed_today", 0))
    wins = sum(1 for r in aggregate_r if r > 0)
    losses = sum(1 for r in aggregate_r if r < 0)
    avg_r_all = float(np.mean(aggregate_r)) if aggregate_r else 0.0
    median_r_all = float(np.median(aggregate_r)) if aggregate_r else 0.0
    std_r_all = float(np.std(aggregate_r)) if len(aggregate_r) >= 2 else 0.0
    confidence_95 = 0.0
    if aggregate_r:
        confidence_95 = 1.96 * (std_r_all / math.sqrt(max(1, len(aggregate_r))))

    return {
        "trades_opened_today": int(daily_trade_budget.get("trades_opened_today", 0)),
        "trades_closed_today": total_closed,
        "win_loss": {
            "wins": wins,
            "losses": losses,
            "breakeven": max(0, total_closed - wins - losses),
            "win_rate": (wins / max(1, total_closed)),
        },
        "r_multiple_distribution": {
            "mean": avg_r_all,
            "median": median_r_all,
            "stddev": std_r_all,
            "mean_95ci": [avg_r_all - confidence_95, avg_r_all + confidence_95],
            "sample_size": len(aggregate_r),
        },
        "strategy_summary": strat_rows,
        "slippage_spread": {ins: execution_stats.summary(ins) for ins in INSTRUMENTS[:10]},
        "top_skip_reasons": skipped[:5],
        "director_accuracy_proxy": {"mode": daily_trade_budget.get("mode", "normal"), "opened": int(daily_trade_budget.get("trades_opened_today", 0))},
    }


async def auto_trader():
    global _last_closeout_date

    while True:
        if AUTO_TRADE_ON_FLAG:
            # Context & (optional) snapshots
            try:
                build_context_blob()
            except Exception:
                pass

            # If you don't have this function, comment it out:
            # try:
            #     record_pnl_snapshot()
            # except Exception:
            #     pass

            # 1) Build world-state and director decision
            try:
                world_state = build_world_state(top_n=12)
                deterministic = build_deterministic_director_decision(world_state)
                heatmap = sorted([(i, m.get("opportunity_score", 0.0)) for i, m in world_state.get("market", {}).items()], key=lambda x: x[1], reverse=True)[:10]
                log_event("INFO", None, "Opportunity heatmap", {"top10": heatmap}, level=2)
                decision, from_llm = await maybe_llm_director(world_state, deterministic)
                director_state["decision"] = decision
                director_state["ts"] = time.time()
                mode = decision.get("quota_plan", {}).get("mode", "normal")
                if mode == "scalp_mode":
                    liq_ok = world_state["session"] in {"LONDON", "NY", "OVERLAP"} and all(m["liquidity_factor"] > 0.55 for m in world_state["market"].values())
                    if not liq_ok:
                        mode = "expand_breadth"
                daily_trade_budget["mode"] = mode
                focus = decision.get("focus", [])
                if mode == "expand_breadth":
                    extra = sorted(world_state["market"].items(), key=lambda x: x[1].get("opportunity_score", 0.0), reverse=True)[:8]
                    seen = {f["instrument"] for f in focus}
                    for ins, _ in extra:
                        if ins in seen:
                            continue
                        focus.append({"instrument": ins, "strategies": list(STRATEGY_CATALOG.keys())[:2], "priority": 0.3, "confidence": 0.4, "reasons": ["quota_expand"]})
                replay_log({"ts": utc_now_iso(), "type": "director", "from_llm": from_llm, "decision": decision, "session": world_state["session"]})
                sess_key = f"{datetime.now(timezone.utc).date().isoformat()}-{world_state['session']}"
                if ops_state.get("last_session") != sess_key:
                    edge_mode = "defensive" if daily_trade_budget.get("consecutive_losses", 0) >= 2 else "normal"
                    ops_state["playbook"] = session_playbook(world_state["session"], focus, edge_mode)
                    ops_state["last_session"] = sess_key
                    replay_log({"ts": utc_now_iso(), "type": "session_playbook", "playbook": ops_state["playbook"]})
            except Exception:
                logger.exception("director build error")
                focus = [{"instrument": i, "strategies": list(STRATEGY_CATALOG.keys())[:2]} for i in INSTRUMENTS[:DIRECTOR_TOP_FOCUS]]
                world_state = None

            # 2) Run focused instruments in parallel
            tasks = [trade_once(item["instrument"], director_item=item, world_state=world_state) for item in focus]
            try:
                await asyncio.gather(*tasks)
            except Exception:
                logger.exception("auto_trader gather error")

            # 2) Trade lifecycle manager + strategy performance updates
            try:
                lifecycle_manager(sl_buffer=0.04)
                update_strategy_performance_from_fills()
            except Exception:
                logger.exception("lifecycle/performance manager error")

            # 3) Hard daily closeout at 17:00 New York (once per day)
            try:
                now_ny = datetime.now(NY_TZ)
                is_closeout_time = (now_ny.hour == CLOSEOUT_HOUR and now_ny.minute == 0)
                if is_closeout_time:
                    today = now_ny.date()
                    if _last_closeout_date != today:
                        closeout_all_positions()
                        write_eod_report(f"reports/eod_{today.isoformat()}.json", generate_eod_payload())
                        _last_closeout_date = today
            except Exception:
                logger.exception("closeout check error")

        # Sleep until next cycle
        await asyncio.sleep(COOLDOWN_SEC)


# ========= DISCORD BOT =========

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    keep_alive()
    try:
        get_instruments_meta()
    except Exception:
        pass
    bot.loop.create_task(auto_trader())

@bot.command(name="status")
async def status(ctx):
    acct = get_account_summary()
    total_pl, win_rate, total_unrealized = compute_pl_winrate()
    sess = current_session_info()
    await ctx.send(
        f"Balance: {acct.get('NAV')} {acct.get('currency')} | "
        f"Total P/L: {total_pl:.2f} | Win Rate: {win_rate:.1f}% | Unrlzd: {total_unrealized:.2f} | Sharpe≈{strategy_sharpe():.2f} | "
        f"Session={sess['session_name']} ({sess['minutes_to_session_change']}m)"
    )
    active = []
    for ins in INSTRUMENTS:
        lp = latest_plan_cache.get(ins, {})
        sel = lp.get("selected") if isinstance(lp, dict) else None
        if sel:
            active.append(f"{ins}:{sel.get('strategy')} {sel.get('side')} rr={sel.get('rr',0):.2f} evr={sel.get('ev_r',0):.2f}")
    active_txt = " | ".join(active[:3]) if active else "no active selected plans"
    await ctx.send(
        f"Balance: {acct.get('NAV')} {acct.get('currency')} | "
        f"Total P/L: {total_pl:.2f} | Win Rate: {win_rate:.1f}% | Unrlzd: {total_unrealized:.2f} | Sharpe≈{strategy_sharpe():.2f} | Plans: {active_txt}"
    )

@bot.command(name="auto")
async def auto(ctx, mode: str):
    """!auto on/off"""
    global AUTO_TRADE_ON_FLAG
    if mode.lower() == "on":
        AUTO_TRADE_ON_FLAG = True
        await ctx.send("Auto-trading: ON")
    elif mode.lower() == "off":
        AUTO_TRADE_ON_FLAG = False
        await ctx.send("Auto-trading: OFF")
    else:
        await ctx.send("Usage: !auto on|off")

@bot.command(name="signal")
async def signal_cmd(ctx, instrument: str):
    instrument = instrument.upper()
    if instrument not in INSTRUMENTS:
        await ctx.send(f"Unknown instrument. Choose from {', '.join(INSTRUMENTS)}")
        return
    sig, px = signal_cache.get(instrument), price_cache.get(instrument)
    lp = latest_plan_cache.get(instrument, {})
    sel = lp.get("selected") if isinstance(lp, dict) else None
    if sel:
        await ctx.send(
            f"{instrument} mid={px} regime={lp.get('snapshot_regime')} strategy={sel.get('strategy')} "
            f"side={sel.get('side')} type={sel.get('order_type')} entry={sel.get('entry_price'):.5f} "
            f"sl={sel.get('stop_loss'):.5f} tp={sel.get('take_profit'):.5f} rr={sel.get('rr'):.2f} evr={sel.get('ev_r'):.2f}"
        )
    else:
        await ctx.send(f"{instrument} mid={px} signal={sig}")

@bot.command(name="positions")
async def positions(ctx):
    pos = get_positions_info()
    if not pos:
        await ctx.send("No open positions.")
        return
    lines = [f"{p['instrument']}: {p['units']} units | UPL: {p['unrealized_pl']:.2f}" for p in pos]
    await ctx.send("\n".join(lines))

@bot.command(name="fillall")
async def fillall(ctx):
    """Fills all pending orders 'as is' by submitting equivalent MARKET orders, then cancels the pending ones."""
    pend = get_pending_orders()
    if not pend:
        await ctx.send("No pending orders.")
        return
    filled = 0
    for o in pend:
        try:
            instr = o["instrument"]
            units = int(o.get("units","0"))
            if units == 0:
                continue
            place_market_order(instr, units)
            oid = o.get("id")
            if oid:
                cancel_order(oid)
            filled += 1
        except Exception as e:
            logger.warning(f"fillall error: {e}")
    await ctx.send(f"Filled {filled} pending orders via market.")

@bot.command(name="context")
async def ctx_cmd(ctx, instrument: str=None):
    """!context <INSTR> → macro, regime, spread guard, events"""
    ins = (instrument or INSTRUMENTS[0]).upper()
    if ins not in INSTRUMENTS:
        ins = INSTRUMENTS[0]
    macro = fetch_macro_context()
    econ = fetch_econ_calendar()
    df = get_candles(ins, count=120)
    reg, mult = compute_intraday_regime(df) if df is not None else ("neutral",1.0)
    guard, spr = spread_liquidity_guard(ins)
    base, quote = ins.split("_")
    mu_rn = RF.get(quote,0.0) - RF.get(base,0.0)
    await ctx.send(
        f"[{ins}] Regime={reg} mult={mult:.2f} | Spread guard={guard} details={spr} | "
        f"DXY bias={(macro.get('DXY_proxy') or {}).get('bias','?')} | Carry(rd-rf)={mu_rn:.4f} | "
        f"NextEvent={(econ[0] if econ else {})}"
    )

@bot.command(name="econ")
async def econ_cmd(ctx):
    ev = fetch_econ_calendar() or []
    lines = []
    for e in ev[:10]:
        lines.append(f"{e.get('when','?')}  {e.get('currency','')}  {e.get('event','')}  cons:{e.get('consensus','')}")
    await ctx.send("\n".join(lines) if lines else "No events.")

@bot.command(name="ffnews")
async def ffnews_cmd(ctx, hours: int = 24):
    """Show Forex Factory news events for the next N hours"""
    events = fetch_forex_factory_events()
    
    if not events:
        await ctx.send("No Forex Factory events found or unable to fetch.")
        return
    
    # Filter events for the requested time window
    now = datetime.now(timezone.utc)
    filtered_events = [e for e in events if (e['time'] - now).total_seconds() <= hours * 3600]
    
    if not filtered_events:
        await ctx.send(f"No Forex Factory events in the next {hours} hours.")
        return
    
    lines = [f"**Forex Factory News (Next {hours}h):**"]
    for i, event in enumerate(filtered_events[:8]):  # Show max 8 events
        time_str = event['time'].strftime("%H:%M UTC")
        impact_emoji = "🔴" if event['impact'] == "High" else "🟠" if event['impact'] == "Medium" else "🟢"
        lines.append(f"{impact_emoji} **{time_str}** {event['currency']} - {event['title']}")
    
    await ctx.send("\n".join(lines))

@bot.command(name="sent")
async def sent_cmd(ctx):
    lines = []
    for ins in INSTRUMENTS:
        s = fetch_positioning(ins)
        lines.append(f"{ins}: skew={s.get('skew',0):+.3f} contrarian={s.get('contrarian','-')}")
    cot = fetch_COT()
    lines.append(f"COT: {cot.get('status','unavailable')}")
    await ctx.send("\n".join(lines))

@bot.command(name="corr")
async def corr_cmd(ctx):
    c = correlation_matrix()
    if "status" in c:
        await ctx.send("Correlation matrix unavailable.")
        return
    tops = ", ".join([f"{x['pair']}:{x['corr']:.2f}" for x in c.get("top",[])])
    bots = ", ".join([f"{x['pair']}:{x['corr']:.2f}" for x in c.get("bottom",[])])
    await ctx.send(f"Top corr: {tops}\nBottom corr: {bots}")

@bot.command(name="risk")
async def risk_cmd(ctx):
    df = get_candles(INSTRUMENTS[0], count=120)
    reg, mult = compute_intraday_regime(df) if df is not None else ("neutral",1.0)
    var_est = portfolio_var(price_cache, horizon_days=1, cl=0.99)
    rv = 0.0
    if df is not None:
        r = np.log(df["c"]/df["c"].shift(1)).dropna()
        rv = float(r.std(ddof=1)*math.sqrt(12*24*252))
    await ctx.send(f"Risk mult={mult:.2f} | VaR99(param)≈{var_est.get('param',0):.4f} | RealizedAnnVol≈{rv:.3f} vs Target={TARGET_ANNUAL_VOL:.3f}")

@bot.command(name="dxy")
async def dxy_cmd(ctx):
    m = fetch_macro_context()
    d = (m.get("DXY_proxy") or {})
    await ctx.send(f"DXY proxy: {d.get('last','?')}, USD bias={d.get('bias','?')}")

@bot.command(name="capm")
async def capm_cmd(ctx, instrument: str):
    instrument = instrument.upper()
    if instrument not in INSTRUMENTS:
        await ctx.send("Unknown instrument.")
        return
    est = compute_beta_alpha(instrument)
    if 'beta' not in est:
        await ctx.send("Not enough data for CAPM.")
        return
    await ctx.send(f"{instrument} CAPM: beta={est['beta']:.3f}, alpha_ann={est['alpha_ann']:.4f}, R2={est['r2']:.3f}")

@bot.command(name="bs")
async def bs_cmd(ctx, instrument: str, K: float, days: int, sigma: float, opttype: str, rd: float, rf: float):
    instrument = instrument.upper()
    S = price_cache.get(instrument)
    if S is None:
        df = get_candles(instrument, 5)
        if df is None:
            await ctx.send("No price available.")
            return
        S = df['c'].iloc[-1]
    T = max(1e-6, days/365.0)
    call = opttype.lower().startswith("c")
    res = garman_kohlhagen(float(S), float(K), T, float(sigma), float(rd), float(rf), call=call)
    await ctx.send(f"{instrument} BS(GK): price={res['price']:.6f} Δ={res['delta']:.4f} Γ={res['gamma']:.6f} vega={res['vega']:.4f} θ={res['theta']:.4f}")

@bot.command(name="black76")
async def black76_cmd(ctx, instrument: str, K: float, days: int, sigma: float, opttype: str, r: float, F: float):
    instrument = instrument.upper()
    T = max(1e-6, days/365.0)
    call = opttype.lower().startswith("c")
    res = black76(float(F), float(K), T, float(sigma), float(r), call=call)
    await ctx.send(f"{instrument} Black76: price={res['price']:.6f} Δ_F={res['deltaF']:.4f} vega={res['vega']:.4f}")

@bot.command(name="sharpe")
async def sharpe_cmd(ctx):
    await ctx.send(f"Strategy Sharpe (approx): {strategy_sharpe():.2f}")

@bot.command(name="var")
async def var_cmd(ctx):
    v = portfolio_var(price_cache, horizon_days=1, cl=0.99)
    await ctx.send(f"Portfolio VaR 1d@99% (param): ≈{v['param']:.4f} (limit {VAR_LIMIT_PCT:.4f})")

# ========= ADVANCED RISK & ANALYTICS COMMANDS =========
@bot.command(name="kelly")
async def kelly_cmd(ctx):
    """Compute Kelly fraction using recent PnL winrate."""
    pnl = fetch_pnl_series(200)
    if pnl.empty:
        await ctx.send("unavailable")
        return
    wins = pnl[pnl > 0]; losses = pnl[pnl < 0]
    if len(wins) < 3 or len(losses) < 3:
        await ctx.send("not enough data")
        return
    win_rate = len(wins) / len(pnl)
    wl_ratio = (wins.mean() / abs(losses.mean())) if abs(losses.mean()) > 0 else 0
    k = kelly_criterion(win_rate, wl_ratio)
    await ctx.send(f"Kelly fraction ≈ {k:.3f} (winrate={win_rate:.2%}, W/L={wl_ratio:.2f})")

@bot.command(name="cvar")
async def cvar_cmd(ctx):
    """Compute Conditional VaR (Expected Shortfall)."""
    pnl = fetch_pnl_series(300)
    if pnl.empty:
        await ctx.send("unavailable")
        return
    es = cvar(pnl, alpha=0.975)
    await ctx.send(f"CVaR(97.5%) ≈ {es:.2f}")

@bot.command(name="mcarisk")
async def mcarisk_cmd(ctx):
    """Monte Carlo VaR estimation."""
    pnl = fetch_pnl_series(300)
    if pnl.empty:
        await ctx.send("unavailable")
        return
    mc = monte_carlo_var(pnl, alpha=0.99, sims=2000)
    await ctx.send(f"Monte Carlo VaR(99%) ≈ {mc:.2f}")

@bot.command(name="sortino")
async def sortino_cmd(ctx):
    """Sortino ratio for recent returns."""
    pnl = fetch_pnl_series(300)
    if pnl.empty:
        await ctx.send("unavailable")
        return
    r = pnl.pct_change().dropna()
    s = sortino_ratio(r)
    await ctx.send(f"Sortino ratio ≈ {s:.3f}")

@bot.command(name="omega")
async def omega_cmd(ctx):
    """Omega ratio for recent returns."""
    pnl = fetch_pnl_series(300)
    if pnl.empty:
        await ctx.send("unavailable")
        return
    r = pnl.pct_change().dropna()
    o = omega_ratio(r)
    await ctx.send(f"Omega ratio ≈ {o:.3f}")

@bot.command(name="tail")
async def tail_cmd(ctx):
    """Tail ratio for recent returns."""
    pnl = fetch_pnl_series(300)
    if pnl.empty:
        await ctx.send("unavailable")
        return
    r = pnl.pct_change().dropna()
    t = tail_ratio(r)
    await ctx.send(f"Tail ratio ≈ {t:.3f}")

@bot.command(name="drawdown")
async def drawdown_cmd(ctx):
    """Max drawdown of cumulative PnL."""
    pnl = fetch_pnl_series(300)
    if pnl.empty:
        await ctx.send("unavailable")
        return
    eq = pnl.cumsum()
    dd = max_drawdown(eq)
    await ctx.send(f"Max Drawdown ≈ {dd*100:.2f}%")

# ========= ADAPTIVE INTELLIGENCE COMMANDS =========
@bot.command(name="trainml")
async def trainml_cmd(ctx, instrument: str = "EUR_USD"):
    """Train the ML alpha model on recent candle data."""
    m = train_ml_model(instrument)
    if m is None:
        await ctx.send("Training failed: not enough data.")
    else:
        await ctx.send(f"ML model trained on {instrument} (Logistic Regression).")

@bot.command(name="pwin")
async def pwin_cmd(ctx, instrument: str):
    """Predict ML probability of next candle being profitable."""
    instr = instrument.upper()
    p = predict_pwin(instr)
    if p is None:
        await ctx.send("Prediction unavailable.")
    else:
        await ctx.send(f"{instr} ML-p(win) ≈ {p:.2%}")

@bot.command(name="autotune")
async def autotune_cmd(ctx):
    """Run auto-calibration of Sharpe & Edge thresholds."""
    pnl = fetch_pnl_series(200)
    if pnl.empty:
        await ctx.send("unavailable")
        return
    auto_calibrate_thresholds(pnl)
    await ctx.send(f"Auto-tuned: edge_min={MIN_EDGE_MULT_COST:.2f}, Sharpe_floor={SHARPE_FLOOR:.2f}")

# ========= QUANT RESEARCH COMMANDS =========
@bot.command(name="season")
async def season_cmd(ctx, instrument: str):
    """Fourier seasonality scan of recent returns."""
    instr = instrument.upper()
    df = get_candles(instr, count=300)
    if df is None:
        await ctx.send("unavailable")
        return
    res = fourier_seasonality_scan(df)
    if not res:
        await ctx.send("insufficient data")
    else:
        await ctx.send(f"{instr} dominant periodicities: {res}")

@bot.command(name="cointeg")
async def cointeg_cmd(ctx, instr1: str, instr2: str):
    """Test pair cointegration."""
    a = instr1.upper(); b = instr2.upper()
    df1 = get_candles(a, count=300)
    df2 = get_candles(b, count=300)
    if df1 is None or df2 is None:
        await ctx.send("unavailable")
        return
    res = cointegration_test(df1["c"], df2["c"])
    if res is None:
        await ctx.send("insufficient data")
        return
    await ctx.send(f"{a}/{b} β={res['beta']:.3f} p={res['pval']:.3f} → {'Cointegrated ✅' if res['cointegrated'] else 'No cointegration ❌'}")

@bot.command(name="volregime")
async def volregime_cmd(ctx, instrument: str):
    """GARCH-lite volatility clustering and regime detection."""
    instr = instrument.upper()
    df = get_candles(instr, count=300)
    if df is None:
        await ctx.send("unavailable")
        return
    gvol = garch_lite_vol(df)
    regime = detect_regime(df)
    await ctx.send(f"{instr} volatility≈{gvol:.6f} | regime={regime}")

@bot.command(name="alog")
async def alog_cmd(ctx, n: int = 25):
    """Show the last N analysis events (default 25). Usage: !alog [n]"""
    n = max(1, min(n, 200))
    events = get_log(n)
    if not events:
        await ctx.send("Analysis log empty.")
        return
    lines = []
    for e in events:
        tag = f"[{e['ts']}] {e['kind']}" + (f"[{e.get('instr')}]" if e.get('instr') else "")
        msg = e.get('msg', '')
        lines.append(f"{tag} — {msg}")
    sender = chunked_send_factory(ctx)
    await sender("\n".join(lines))

@bot.command(name="loglevel")
async def loglevel_cmd(ctx, level: int):
    """Set analysis log verbosity: 0=quiet, 1=basic, 2=detailed, 3=trace"""
    global LOG_VERBOSITY
    LOG_VERBOSITY = int(max(0, min(3, level)))
    await ctx.send(f"LOG_VERBOSITY set to {LOG_VERBOSITY}")

# ========= EXTRA HELPERS / STATE FOR COMMANDS =========
auth_sessions = set()              # user_ids with active admin auth
roles = defaultdict(lambda: "viewer")  # user_id -> "viewer" | "trader"
trail_rules = {}                   # {instr: {"mult": float}}
slice_sched = {}                   # {id: {"instr":..., "remaining":..., "clip":..., "sec":..., "next_ts":...}}
alerts = []                        # [{"user_id":..., "instr":..., "cond": ("price", ">", 1.1000), "ttl_ts":...}]
subscriptions = defaultdict(set)   # user_id -> {"events","context"}
force_bypass = set()               # user_ids temporarily allowed to bypass gates
_sched_counter = 0

def is_admin(user_id:int)->bool:
    return (str(user_id) in roles and roles[str(user_id)]=="trader") or (user_id in auth_sessions)

def gate_reasons(instr, use_force=False):
    """Return (OK:bool, reasons:set[str]) using current caches and fast checks."""
    reasons=set()
    if not use_force:
        # spread / stale
        spr_block, _info = spread_liquidity_guard(instr)
        if spr_block: reasons.add("Spread")
        # events
        if event_guardrails(instr): reasons.add("Event")
        # VaR
        var_est = portfolio_var(price_cache, horizon_days=1, cl=0.99)
        if var_est.get("param", 0) > VAR_LIMIT_PCT: reasons.add("VaR")
        # Sharpe
        if strategy_sharpe() < SHARPE_FLOOR: reasons.add("Sharpe")
        # Score
        sig = signal_cache.get(instr, {})
        score = 0.0 if not isinstance(sig, dict) else float(sig.get("score", 0.0))
        if abs(score) < 0.25: reasons.add("Score")
    return (len(reasons)==0), reasons

def chunked_send_factory(ctx):
    async def _send(txt):
        if len(txt)<=1800:
            await ctx.send(txt)
            return
        i=0
        while i<len(txt):
            await ctx.send(txt[i:i+1800])
            i+=1800
    return _send

def parse_cond(cond:str):
    """Parse 'price>1.1000' or 'score>0.6'"""
    for key in ("price","score"):
        for op in (">=","<=","==",">","<"):
            token=f"{key}{op}"
            if cond.startswith(token):
                try:
                    val=float(cond[len(token):])
                except:
                    return None
                return (key, op, val)
    return None

def eval_cond(instr, ctuple):
    key, op, val = ctuple
    if key=="price":
        x = price_cache.get(instr)
    else:
        sig = signal_cache.get(instr, {})
        x = float(sig.get("score", 0.0)) if isinstance(sig, dict) else 0.0
    if x is None: return False
    if op=="==": return x==val
    if op==">":  return x>val
    if op=="<":  return x<val
    if op==">=": return x>=val
    if op=="<=": return x<=val
    return False

def get_last_tick_age(instr):
    if not spread_history[instr]:
        return None
    return time.time() - spread_history[instr][-1][0]

def approx_slippage_stats(n=100):
    """Estimate slippage from last n fills: compare fill price vs mid around that time (approx)."""
    tx = safe_get(f"{HOST}/accounts/{OANDA_ACCOUNTID}/transactions") or {}
    rows = [t for t in tx.get("transactions",[]) if t.get("type")=="ORDER_FILL"]
    rows = rows[-n:]
    slips=[]
    for t in rows:
        try:
            price = float(t.get("price",0))
            instr = t.get("instrument","")
            # use cached mid
            mid = price_cache.get(instr)
            if mid:
                slips.append(abs(price-mid)/mid)
        except: pass
    if not slips: return None
    arr=np.array(slips)
    return float(np.mean(arr)), float(np.quantile(arr, 0.95))

def close_units(instr, units):
    """Market-close 'units' (positive reduces long / opens short). Use signed units."""
    if units==0: return None
    return place_market_order(instr, -units)  # placing opposite to reduce

def net_units(instr):
    units=0
    for t in get_open_trades(instr):
        try:
            units += int(t.get("currentUnits",0))
        except: pass
    return units

def twap_schedule(instr, total_units, minutes):
    global _sched_counter
    clips = max(1, minutes)  # 1 clip per minute
    clip = int(total_units / clips)
    if clip==0: clip = 1 if total_units>0 else -1
    _sched_counter += 1
    sid = f"twap-{_sched_counter}"
    slice_sched[sid] = {"instr": instr, "remaining": int(total_units), "clip": int(clip), "sec": 60, "next_ts": time.time()+60}
    return sid, clips, clip

def iceberg_schedule(instr, total_units, clip, sec):
    global _sched_counter
    _sched_counter += 1
    sid = f"ice-{_sched_counter}"
    slice_sched[sid] = {"instr": instr, "remaining": int(total_units), "clip": int(clip), "sec": int(sec), "next_ts": time.time()+int(sec)}
    return sid

async def _run_schedules_once():
    """Lightweight scheduler: send clips if time. Obeys gates."""
    now=time.time()
    to_del=[]
    for sid, sch in list(slice_sched.items()):
        if now < sch["next_ts"]: 
            continue
        instr=sch["instr"]; clip=sch["clip"]; rem=sch["remaining"]
        ok, reasons = gate_reasons(instr)
        if not ok:
            # push next attempt
            sch["next_ts"]=now+sch["sec"]
            continue
        # execute one clip
        units = clip if abs(clip)<=abs(rem) else rem
        place_market_order(instr, units)
        sch["remaining"] = rem - units
        sch["next_ts"]=now+sch["sec"]
        if sch["remaining"]==0 or (rem>0 and sch["remaining"]<0) or (rem<0 and sch["remaining"]>0):
            to_del.append(sid)
    for sid in to_del:
        slice_sched.pop(sid, None)


# ========= RESEARCH / REPLAY ENGINE =========

class ReplayMarketDataProvider:
    def __init__(self, candles_by_instr):
        self.data = {}
        for ins, df in candles_by_instr.items():
            t = df.copy()
            t["time"] = pd.to_datetime(t["time"], utc=True)
            self.data[ins] = t.sort_values("time").reset_index(drop=True)

    def _resample(self, df, timeframe):
        if timeframe == "M5":
            return df
        rule = {"M15": "15min", "H1": "1h"}.get(timeframe, "5min")
        return (
            df.set_index("time")
              .resample(rule)
              .agg({"o":"first","h":"max","l":"min","c":"last","v":"sum"})
              .dropna()
              .reset_index()
        )

    def get_window(self, instrument, timeframe, end_idx, bars):
        base = self.data[instrument].iloc[: end_idx + 1]
        return self._resample(base, timeframe).tail(bars).copy()


class ReplayExecutionProvider:
    def execute(self, plan, next_bar, spread):
        side = 1 if plan["direction"] > 0 else -1
        slip = spread / 2.0
        t = plan.get("type", "MARKET")
        if t == "MARKET":
            return {"filled": True, "entry_price": float(next_bar["o"]) + side * slip}
        if t == "LIMIT":
            touched = next_bar["l"] <= plan["price"] <= next_bar["h"]
            return {"filled": touched, "entry_price": float(plan["price"] + side * 0.1 * slip)}
        if t == "STOP":
            touched = next_bar["l"] <= plan["price"] <= next_bar["h"]
            return {"filled": touched, "entry_price": float(plan["price"] + side * slip)}
        return {"filled": False}


class ProbabilityCalibratorWF:
    def __init__(self):
        self.model = LogisticRegression(max_iter=200)
        self.iso = IsotonicRegression(out_of_bounds="clip")
        self.ready = False

    def fit(self, p_raw, y):
        x = np.asarray(p_raw).reshape(-1, 1)
        y = np.asarray(y).astype(int)
        if len(np.unique(y)) < 2:
            self.ready = False
            return
        self.model.fit(x, y)
        p = self.model.predict_proba(x)[:, 1]
        self.iso.fit(p, y)
        self.ready = True

    def predict_one(self, p_raw):
        if not self.ready:
            return float(p_raw)
        p = self.model.predict_proba(np.array([[float(p_raw)]]))[:, 1][0]
        return float(self.iso.predict([p])[0])


class QuantileHeadWF:
    def __init__(self):
        self.models = {
            "q10": GradientBoostingRegressor(loss="quantile", alpha=0.1, random_state=7),
            "q50": GradientBoostingRegressor(loss="quantile", alpha=0.5, random_state=7),
            "q90": GradientBoostingRegressor(loss="quantile", alpha=0.9, random_state=7),
        }
        self.ready = False

    def fit(self, X, y):
        X = np.asarray(X)
        y = np.asarray(y)
        if len(y) < 30:
            self.ready = False
            return
        for m in self.models.values():
            m.fit(X, y)
        self.ready = True

    def predict_one(self, x):
        if not self.ready:
            return {"q10": 0.0, "q50": 0.0, "q90": 0.0}
        x = np.asarray(x).reshape(1, -1)
        return {k: float(m.predict(x)[0]) for k, m in self.models.items()}


def wf_features(df_m5):
    r = np.log(df_m5["c"] / df_m5["c"].shift(1)).dropna()
    return np.array([
        float(r.tail(6).mean() if len(r) else 0.0),
        float(r.tail(20).std() if len(r) else 0.0),
        float((df_m5["c"].iloc[-1] / (df_m5["c"].iloc[-20] + 1e-9)) - 1.0),
        float((df_m5["h"].tail(10).max() - df_m5["l"].tail(10).min()) / (df_m5["c"].iloc[-1] + 1e-9)),
    ])


def run_research_backtest(data_dir, out_dir="research_outputs", wf_state_path=WF_STATE_PATH):
    candles = {}
    for f in Path(data_dir).glob("*.csv"):
        candles[f.stem] = pd.read_csv(f)
    if not candles:
        raise RuntimeError("No CSV candles found")

    profiles = {
        "conservative": {"min_score": 0.35, "min_rr": 1.25, "min_pwin": 0.57, "time_stop_bars": 6},
        "default": {"min_score": 0.25, "min_rr": 1.00, "min_pwin": 0.52, "time_stop_bars": 6},
        "aggressive": {"min_score": 0.15, "min_rr": 0.90, "min_pwin": 0.50, "time_stop_bars": 8},
    }

    md = ReplayMarketDataProvider(candles)
    ex = ReplayExecutionProvider()

    def simulate_profile(df, profile_name, profile, start_i, end_i, cal, qh, instrument):
        trades = []
        eq = [1.0]
        calib = []
        q_last = {"q10": 0.0, "q50": 0.0, "q90": 0.0}
        for i in range(start_i, min(end_i, len(df) - 8)):
            w = md.get_window(instrument, "M5", i, 120)
            x = wf_features(w)
            q = qh.predict_one(x)
            q_last = q
            raw_p = float((np.tanh(x[0] / (x[1] + 1e-9)) + 1.0) / 2.0)
            cal_p = cal.predict_one(raw_p)
            score = float(np.tanh(x[0] / (x[1] + 1e-9)))
            if abs(score) < profile["min_score"] or cal_p < profile["min_pwin"]:
                continue
            direction = 1 if score > 0 else -1
            if (direction > 0 and q["q50"] <= 0) or (direction < 0 and q["q50"] >= 0):
                continue
            rr = abs(q["q90"]) / max(abs(q["q10"]), 1e-6)
            if rr < profile["min_rr"]:
                continue

            entry_ref = float(df["c"].iloc[i])
            sl = entry_ref * (1.0 + (q["q10"] if direction > 0 else q["q90"]))
            tp = entry_ref * (1.0 + (q["q90"] if direction > 0 else q["q10"]))
            spread_mult = 1.8 if pd.to_datetime(df["time"].iloc[i]).hour in (21, 22, 23, 0, 1) else 1.0
            spread = float(entry_ref * 0.00006 * spread_mult)
            fill = ex.execute({"type": "MARKET", "direction": direction}, df.iloc[i + 1], spread)
            if not fill.get("filled"):
                continue
            entry = float(fill["entry_price"])

            exit_px = float(df["c"].iloc[i + 6])
            exit_t = str(df["time"].iloc[i + 6])
            for j in range(i + 1, min(i + 7, len(df))):
                hi, lo = float(df["h"].iloc[j]), float(df["l"].iloc[j])
                if direction > 0 and lo <= sl:
                    exit_px = sl - spread / 2
                    exit_t = str(df["time"].iloc[j])
                    break
                if direction > 0 and hi >= tp:
                    exit_px = tp - spread / 2
                    exit_t = str(df["time"].iloc[j])
                    break
                if direction < 0 and hi >= sl:
                    exit_px = sl + spread / 2
                    exit_t = str(df["time"].iloc[j])
                    break
                if direction < 0 and lo <= tp:
                    exit_px = tp + spread / 2
                    exit_t = str(df["time"].iloc[j])
                    break

            risk = max(abs(entry - sl), 1e-9)
            r_mult = direction * (exit_px - entry) / risk
            eq.append(eq[-1] * (1.0 + 0.01 * r_mult))
            trades.append({
                "instrument": instrument,
                "strategy": "core",
                "profile": profile_name,
                "direction": direction,
                "entry_time": str(df["time"].iloc[i + 1]),
                "entry_price": entry,
                "exit_time": exit_t,
                "exit_price": exit_px,
                "spread_cost": spread,
                "fees": 0.0,
                "r_multiple": r_mult,
                "raw_pwin": raw_p,
                "calibrated_pwin": cal_p,
                "q10": q["q10"],
                "q50": q["q50"],
                "q90": q["q90"],
            })
            calib.append({"raw_pwin": raw_p, "calibrated_pwin": cal_p, "y": 1 if r_mult > 0 else 0, "r": r_mult})
        return trades, eq, calib, q_last

    all_trades = []
    equity = [1.0]
    calib_rows = []
    q_runtime = {"instrument": {}}
    wf_rows = []

    for ins, df in md.data.items():
        if len(df) < 260:
            continue

        # model training set for quantiles + calibration
        X_train, y_train, p_train = [], [], []
        for i in range(60, min(180, len(df) - 7)):
            w = md.get_window(ins, "M5", i, 120)
            x = wf_features(w)
            fwd = float(df["c"].iloc[i + 6] / (df["c"].iloc[i] + 1e-9) - 1.0)
            raw = float((np.tanh(x[0] / (x[1] + 1e-9)) + 1.0) / 2.0)
            X_train.append(x)
            y_train.append(fwd)
            p_train.append(raw)

        cal = ProbabilityCalibratorWF()
        qh = QuantileHeadWF()
        qh.fit(X_train, y_train)
        y_bin = (np.array(y_train) > 0).astype(int)
        cal.fit(p_train, y_bin)

        # walk-forward: rolling train 30 days / test 5 days in M5 bars
        train_bars = 30 * 24 * 12
        test_bars = 5 * 24 * 12
        start = max(180, len(df) - (train_bars + 3 * test_bars))
        stable_changes = 0
        last_selected = None

        while start + train_bars + test_bars < len(df) - 8:
            train_start = start
            train_end = start + train_bars
            test_end = train_end + test_bars

            profile_scores = []
            for pname, prof in profiles.items():
                tr_trades, tr_eq, _, _ = simulate_profile(df, pname, prof, train_start, train_end, cal, qh, ins)
                if not tr_trades:
                    profile_scores.append({"profile": pname, "expectancy": -999.0, "max_drawdown": -1.0, "trades": 0})
                    continue
                tr_df = pd.DataFrame(tr_trades)
                exp = float(tr_df["r_multiple"].mean())
                dd = float((pd.Series(tr_eq) / pd.Series(tr_eq).cummax() - 1.0).min())
                tr_count = int(len(tr_df))
                if tr_count < 8:
                    exp -= 0.2
                if dd < -0.10:
                    exp -= 0.1
                profile_scores.append({"profile": pname, "expectancy": exp, "max_drawdown": dd, "trades": tr_count})

            score_tbl = pd.DataFrame(profile_scores).sort_values(["expectancy", "max_drawdown"], ascending=[False, False])
            selected = score_tbl.iloc[0]["profile"] if not score_tbl.empty else "default"
            if last_selected is not None and selected != last_selected:
                stable_changes += 1
            last_selected = selected

            te_trades, te_eq, te_calib, q_last = simulate_profile(df, selected, profiles[selected], train_end, test_end, cal, qh, ins)
            if te_trades:
                all_trades.extend(te_trades)
                for x in te_eq[1:]:
                    equity.append(equity[-1] * (x / te_eq[0]))
                calib_rows.extend([{"strategy": "core", "instrument": ins, **c} for c in te_calib])
                q_runtime["instrument"][ins] = q_last
                te_df = pd.DataFrame(te_trades)
                wf_rows.append({
                    "instrument": ins,
                    "selected_profile": selected,
                    "oos_expectancy": float(te_df["r_multiple"].mean()),
                    "oos_trades": int(len(te_df)),
                    "stability_changes": stable_changes,
                })

            start += test_bars

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ledger = pd.DataFrame(all_trades)
    ledger.to_csv(out / "trade_ledger.csv", index=False)
    ledger.to_json(out / "trade_ledger.json", orient="records")
    pd.DataFrame({"equity": equity}).to_csv(out / "equity_curve.csv", index=False)

    stats = {}
    if not ledger.empty:
        g = ledger
        win_rate = float((g["r_multiple"] > 0).mean())
        avg_r = float(g["r_multiple"].mean())
        dd = float((pd.Series(equity) / pd.Series(equity).cummax() - 1.0).min())
        loss_sum = abs(float(g[g["r_multiple"] <= 0]["r_multiple"].sum()))
        pf = float(g[g["r_multiple"] > 0]["r_multiple"].sum() / (loss_sum if loss_sum > 0 else 1e-9))
        trades_per_day = float(len(g) / max(1, pd.to_datetime(g["entry_time"]).dt.date.nunique()))
        stats["core"] = {
            "win_rate": win_rate,
            "avg_r": avg_r,
            "expectancy": avg_r,
            "max_drawdown": dd,
            "profit_factor": pf,
            "trades_per_day": trades_per_day,
            "trades": int(len(g)),
        }

    cal_df = pd.DataFrame(calib_rows)
    if not cal_df.empty:
        brier_raw = float(brier_score_loss(cal_df["y"], np.clip(cal_df["raw_pwin"], 1e-6, 1 - 1e-6)))
        brier_cal = float(brier_score_loss(cal_df["y"], np.clip(cal_df["calibrated_pwin"], 1e-6, 1 - 1e-6)))
        bins = np.linspace(0, 1, 6)
        cal_df["bin"] = pd.cut(cal_df["calibrated_pwin"], bins=bins, include_lowest=True)
        reliability = []
        for b, grp in cal_df.groupby("bin", observed=False):
            if len(grp) == 0:
                continue
            reliability.append({"bin": str(b), "pred": float(grp["calibrated_pwin"].mean()), "realized": float(grp["y"].mean()), "n": int(len(grp))})
    else:
        brier_raw = brier_cal = 0.25
        reliability = []

    a_coef = 1.0
    b_coef = 0.0
    if not cal_df.empty and cal_df["y"].nunique() > 1:
        lr = LogisticRegression(max_iter=200)
        lr.fit(np.array(cal_df["raw_pwin"]).reshape(-1, 1), np.array(cal_df["y"]).astype(int))
        a_coef = float(lr.coef_[0][0])
        b_coef = float(lr.intercept_[0])

    (out / "stats.json").write_text(json.dumps(stats, indent=2))
    (out / "calibration.json").write_text(json.dumps({
        "strategy": {
            "core": {
                "a": a_coef,
                "b": b_coef,
                "brier_raw": brier_raw,
                "brier_calibrated": brier_cal,
                "reliability_bins": reliability,
            }
        }
    }, indent=2))
    (out / "quantile_runtime.json").write_text(json.dumps(q_runtime, indent=2))

    wf_df = pd.DataFrame(wf_rows)
    if wf_df.empty:
        selected_profile = "default"
        oos_exp = 0.0
        enabled = False
        stability_changes = 0
    else:
        prof_summary = wf_df.groupby("selected_profile", as_index=False).agg(
            oos_expectancy=("oos_expectancy", "mean"),
            oos_trades=("oos_trades", "sum"),
            stability_changes=("stability_changes", "max"),
        ).sort_values(["oos_expectancy", "oos_trades"], ascending=[False, False])
        top = prof_summary.iloc[0]
        selected_profile = str(top["selected_profile"])
        oos_exp = float(top["oos_expectancy"])
        enabled = bool(oos_exp > 0 and int(top["oos_trades"]) >= 10)
        stability_changes = int(top["stability_changes"])

    wf_state = {
        "generated_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "profiles": profiles,
        "strategies": {
            "core": {
                "selected_profile": selected_profile,
                "oos_expectancy": oos_exp,
                "enabled": enabled,
                "stability_changes": stability_changes,
            }
        }
    }
    Path(wf_state_path).write_text(json.dumps(wf_state, indent=2))
    print("Research run done.")


# ========= MAIN =========

def main():
    if "--research" in sys.argv:
        idx = sys.argv.index("--research")
        data_dir = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else os.environ.get("RESEARCH_DATA_DIR", "")
        if not data_dir:
            raise RuntimeError("Provide data dir: python main.py --research <dir>")
        run_research_backtest(data_dir=data_dir, out_dir=os.environ.get("RESEARCH_OUT_DIR", "research_outputs"), wf_state_path=WF_STATE_PATH)
        return
    if not all([DISCORD_TOKEN, OANDA_API_KEY, OANDA_ACCOUNTID]):
        raise RuntimeError("Missing environment variables...")
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
