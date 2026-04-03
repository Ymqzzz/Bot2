from __future__ import annotations

import main


def _snapshot(liq=0.8, mode="trend", event_block=False, spread_block=False, spread_pct=20.0):
    return {
        "instrument": "EUR_USD",
        "mid": 1.1,
        "atr": 0.001,
        "atr_pct": 0.002,
        "ema20": 1.1,
        "ema50": 1.1,
        "zscore": 0.2,
        "compression": 0.8,
        "breakout": {"dir": 1, "level": 1.101, "mag": 0.5},
        "lux": {"lux_draw": 0.3},
        "regime": "normal",
        "mode": mode,
        "risk_mult": 1.0,
        "spread_block": spread_block,
        "spread_info": {"percentile": spread_pct, "stale": False},
        "liq_factor": liq,
        "event_block": event_block,
        "mtf_votes": {"H1": 1},
        "created_ts": 0,
        "dfs": {"M5": __import__("pandas").DataFrame({"c": [1.0 + i * 0.0001 for i in range(250)]}), "M15": [], "H1": []},
        "htf_align": 0.6,
        "pos_book": {"crowding": 0.0},
    }


def _plan(strategy: str, ev=1.0, conf=0.7):
    return {
        "instrument": "EUR_USD",
        "strategy": strategy,
        "ev_r": ev,
        "rr": 2.0,
        "confidence": conf,
        "side": "BUY",
        "entry_price": 1.1,
        "stop_loss": 1.099,
        "take_profit": 1.102,
    }


def test_main_world_state_attaches_snapshot(monkeypatch):
    monkeypatch.setattr(main, "INSTRUMENTS", ["EUR_USD"])
    monkeypatch.setattr(main, "reset_daily_trade_budget_if_needed", lambda: None)
    monkeypatch.setattr(main, "refresh_pricing_once", lambda: None)
    monkeypatch.setattr(main, "get_nav", lambda: (100_000.0, "USD"))
    monkeypatch.setattr(main, "get_positions_info", lambda: [])
    monkeypatch.setattr(main, "portfolio_var", lambda *_args, **_kwargs: {"param": 0.01})
    monkeypatch.setattr(main, "current_portfolio_heat", lambda _nav: 0.1)
    monkeypatch.setattr(main, "currency_exposure_map", lambda: {"USD": 0.2})
    monkeypatch.setattr(main, "compute_day_realized_pnl", lambda: 0.0)
    monkeypatch.setattr(main, "strategy_sharpe", lambda: 0.0)
    monkeypatch.setattr(main, "build_market_snapshot", lambda _ins: _snapshot())

    ws = main.build_world_state(top_n=1)

    assert "EUR_USD" in ws["market"]
    assert "snapshot" in ws["market"]["EUR_USD"]


def test_strategy_router_reads_intelligence_fields_and_ranks(monkeypatch):
    monkeypatch.setattr(main, "strategy_enabled", lambda _name: True)
    monkeypatch.setattr(main, "plan_passes_gates", lambda _plan, _snap: (True, "OK"))
    monkeypatch.setattr(
        main,
        "candidate_plans_from_snapshot",
        lambda _snapshot, allowed_impl=None: [
            _plan("Range-MeanReversion", ev=0.9, conf=0.7),
            _plan("Trend-Pullback", ev=1.0, conf=0.8),
        ],
    )

    chosen_high, _ = main.strategy_router("EUR_USD", _snapshot(liq=0.95, mode="trend"))
    chosen_low, _ = main.strategy_router("EUR_USD", _snapshot(liq=0.40, mode="trend"))

    assert chosen_high["rank"] > chosen_low["rank"]
    assert chosen_high["strategy"] == "Trend-Pullback"  # range plan gets mismatch penalty in trend mode


def test_strict_quality_gate_blocks_trades_when_configured(monkeypatch):
    monkeypatch.setattr(main, "TRADE_HARD_MAX", 10)
    monkeypatch.setattr(main, "MIN_PLAN_RR", 1.2)
    monkeypatch.setattr(main, "MIN_PLAN_EVR", 0.2)
    monkeypatch.setattr(main, "daily_trade_budget", {"trades_opened_today": 0})
    monkeypatch.setattr(main, "spread_percentile_guard", lambda _instr: (False, {}))

    ok_event, reason_event = main.plan_passes_gates(_plan("Trend-Pullback", ev=1.0), _snapshot(event_block=True))
    ok_spread, reason_spread = main.plan_passes_gates(_plan("Trend-Pullback", ev=1.0), _snapshot(spread_block=True))

    assert not ok_event and reason_event == "Event"
    assert not ok_spread and reason_spread == "Spread"


def test_strategy_sharpe_positive_for_consistent_positive_returns(monkeypatch):
    series = [0.0015 + ((i % 3) - 1) * 0.0002 for i in range(80)]
    monkeypatch.setattr(main, "strategy_return_history", __import__("collections").deque(series, maxlen=252))
    assert main.strategy_sharpe() > 0.0


def test_strategy_sharpe_returns_zero_for_insufficient_history(monkeypatch):
    monkeypatch.setattr(main, "strategy_return_history", __import__("collections").deque([0.002], maxlen=252))
    assert main.strategy_sharpe() == 0.0
