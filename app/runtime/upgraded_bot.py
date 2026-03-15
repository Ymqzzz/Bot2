from __future__ import annotations

from dataclasses import dataclass
import time

from app.config.settings import BotSettings
from app.data.quality import validate_bars_quality
from app.config.validation import validate_settings
from app.features.price_features import compute_price_features
from app.governance.decision_graph import DecisionGraph
from app.governance.kill_switch import KillSwitch
from app.governance.policy_engine import policy_check
from app.models.calibration import ScoreCalibrator
from app.models.ensemble import choose_best_candidate
from app.monitoring.audit import AuditSink
from app.monitoring.events import EventBus
from app.monitoring.repository import create_event_repository
from app.risk.governors import GovernorState, RiskGovernor
from app.risk.portfolio_adapter import PortfolioContext
from app.risk.sizing import PositionSizer
from app.risk.tail_risk import dislocation_score
from app.strategy.registry import StrategyRegistry
from app.strategy.plugins.breakout_plugin import BreakoutPlugin
from app.strategy.plugins.mean_reversion_plugin import MeanReversionPlugin
from app.strategy.plugins.trend_plugin import TrendPlugin


@dataclass
class BrokerContext:
    nav: float
    open_positions: list[dict]
    corr_matrix: dict
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    equity_now: float = 0.0


class UpgradedBot:
    def __init__(self, settings: BotSettings | None = None):
        self.settings = settings or BotSettings.from_env()
        validate_settings(self.settings)
        self.registry = StrategyRegistry()
        self.registry.register(TrendPlugin())
        self.registry.register(MeanReversionPlugin())
        self.registry.register(BreakoutPlugin())
        event_repo = create_event_repository(self.settings.monitoring_events_db_url)
        self.events = EventBus(repository=event_repo, cache_size=self.settings.monitoring_cache_size)
        self.audit = AuditSink()
        self.decision_graph = DecisionGraph(self.events, self.audit)
        self.kill_switch = KillSwitch()
        self.risk_governor = RiskGovernor(max_trades=50)
        self.calibrator = ScoreCalibrator()
        self.sizer = PositionSizer()
        self.gov_state = GovernorState()
        self._last_trade_ts = 0.0

    def _refresh_governor_state(self, broker_ctx: BrokerContext) -> dict[str, float]:
        state = self.gov_state
        state.realized_pnl = broker_ctx.realized_pnl
        state.unrealized_pnl = broker_ctx.unrealized_pnl
        state.equity_now = broker_ctx.equity_now if broker_ctx.equity_now > 0 else broker_ctx.nav
        if state.equity_peak <= 0:
            state.equity_peak = state.equity_now
        else:
            state.equity_peak = max(state.equity_peak, state.equity_now)
        if state.equity_peak > 0:
            state.intraday_drawdown_pct = max(0.0, (state.equity_peak - state.equity_now) / state.equity_peak)
        else:
            state.intraday_drawdown_pct = 0.0
        state.loss_streak = state.loss_streak + 1 if state.daily_pnl < 0 else 0
        return {
            "realized_pnl": state.realized_pnl,
            "unrealized_pnl": state.unrealized_pnl,
            "daily_pnl": state.daily_pnl,
            "equity_now": state.equity_now,
            "equity_peak": state.equity_peak,
            "current_drawdown_pct": state.intraday_drawdown_pct,
            "loss_streak": state.loss_streak,
            "trades_today": state.trades_today,
        }

    def _regime(self, bars: list[dict]) -> str:
        d = dislocation_score(bars, 50.0)
        if d > 1.6:
            return "stress"
        if d < 0.6:
            return "calm"
        return "normal"

    def build_candidates(self, instrument: str, bars: list[dict]) -> tuple[list, dict]:
        feats = compute_price_features(bars)
        return self.registry.generate_candidates(instrument, bars, feats), feats

    def run_cycle(self, market_data, broker_ctx: BrokerContext) -> list[dict]:
        active, reason = self.kill_switch.status()
        if active:
            trace = self.events.new_trace()
            self.events.emit("signal_rejected", trace, {"reason": f"kill_switch:{reason}"})
            return []

        state_snapshot = self._refresh_governor_state(broker_ctx)
        trace = self.events.new_trace()
        self.events.emit("risk_state_updated", trace, state_snapshot)

        ok, why, metrics = self.risk_governor.check(self.gov_state, nav=broker_ctx.nav)
        if not ok:
            block_payload = {
                "reason": why,
                "current_drawdown_pct": metrics["current_drawdown_pct"],
                "loss_budget_usage_pct": metrics["loss_budget_usage_pct"],
                "loss_budget": metrics["loss_budget"],
                "loss_used": metrics["loss_used"],
            }
            self.events.emit("risk_blocked", trace, block_payload)
            return []

        decisions = []
        for instrument in self.settings.instruments:
            bars = market_data.get_recent_bars(instrument, self.settings.granularity, count=150)
            if len(bars) < 40:
                continue
            spread_pctile = market_data.get_spread_pctile(instrument)
            quality = validate_bars_quality(instrument=instrument, bars=bars, spread_pctile=spread_pctile)
            trace = self.events.new_trace()
            if quality.status == "blocked":
                self.events.emit(
                    "data_quality_block",
                    trace,
                    {
                        "instrument": instrument,
                        "failing_rules": quality.failing_rules,
                        "reason_codes": quality.reason_codes,
                    },
                )
                continue
            if quality.status == "degraded":
                self.events.emit(
                    "data_quality_degraded",
                    trace,
                    {
                        "instrument": instrument,
                        "failing_rules": quality.failing_rules,
                        "reason_codes": quality.reason_codes,
                    },
                )
            else:
                self.events.emit("data_quality_pass", trace, {"instrument": instrument, "failing_rules": []})

            liq = market_data.get_liquidity_factor(instrument)
            near_event = market_data.has_near_event(instrument)
            disloc = dislocation_score(bars, spread_pctile)
            pass_policy, reason = policy_check(
                spread_pctile=spread_pctile,
                dislocation=disloc,
                near_event=near_event,
                max_spread_pctile=self.settings.max_spread_pctile,
            )
            if not pass_policy:
                trace = self.events.new_trace()
                self.events.emit("signal_rejected", trace, {"instrument": instrument, "reason": reason, "dislocation": disloc})
                continue

            cands, feats = self.build_candidates(instrument, bars)
            regime = self._regime(bars)
            pwin_map = {i: self.calibrator.calibrate(c.score, regime=regime) for i, c in enumerate(cands)}
            best = choose_best_candidate(cands, pwin_map)
            if best is None:
                continue

            now = time.time()
            if now - self._last_trade_ts < self.settings.min_trade_interval_sec:
                continue
            sizing = self.sizer.compute_units(
                side=best.side,
                nav=broker_ctx.nav,
                entry_price=best.entry_price,
                stop_loss=best.stop_loss,
                atr=float(feats.get("atr", 0.0)),
                dislocation=disloc,
                spread_pctile=spread_pctile,
                confidence=best.score,
                open_positions=broker_ctx.open_positions,
                daily_risk_pct=self.settings.risk_budget_daily,
                cluster_risk_pct=self.settings.cluster_risk_cap,
            )
            if sizing.signed_units == 0:
                trace = self.events.new_trace()
                self.events.emit("signal_rejected", trace, {"instrument": instrument, "reason": "size_zero", "sizing": sizing.to_dict()})
                continue
            trace = self.events.new_trace()
            decision = self.decision_graph.evaluate(
                trace_id=trace,
                candidate=best,
                spread_pctile=spread_pctile,
                liquidity_factor=liq,
                has_near_event=near_event,
                signed_units=sizing.signed_units,
                sizing_diagnostics=sizing.to_dict(),
                portfolio_ctx=PortfolioContext(
                    open_positions=broker_ctx.open_positions,
                    nav=broker_ctx.nav,
                    corr_matrix=broker_ctx.corr_matrix,
                ),
                min_score=self.settings.min_signal_score,
                max_spread_pctile=self.settings.max_spread_pctile,
                daily_risk_pct=self.settings.risk_budget_daily,
                cluster_risk_pct=self.settings.cluster_risk_cap,
            )
            decision["regime"] = regime
            decision["dislocation"] = disloc
            decision["data_quality_status"] = quality.status
            decision["data_quality_reason_codes"] = quality.reason_codes
            if decision.get("approved"):
                self._last_trade_ts = now
                self.gov_state.trades_today += 1
            decisions.append(decision)
        return decisions
