from __future__ import annotations

from dataclasses import dataclass
import time

from app.config.settings import BotSettings
from app.config.validation import validate_settings
from app.features.price_features import compute_price_features
from app.governance.decision_graph import DecisionGraph
from app.governance.kill_switch import KillSwitch
from app.governance.policy_engine import policy_check
from app.models.calibration import ScoreCalibrator
from app.models.ensemble import choose_best_candidate
from app.monitoring.audit import AuditSink
from app.monitoring.events import EventBus
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


class UpgradedBot:
    def __init__(self, settings: BotSettings | None = None):
        self.settings = settings or BotSettings.from_env()
        validate_settings(self.settings)
        self.registry = StrategyRegistry()
        self.registry.register(TrendPlugin())
        self.registry.register(MeanReversionPlugin())
        self.registry.register(BreakoutPlugin())
        self.events = EventBus()
        self.audit = AuditSink()
        self.decision_graph = DecisionGraph(self.events, self.audit)
        self.kill_switch = KillSwitch()
        self.risk_governor = RiskGovernor(max_trades=50)
        self.calibrator = ScoreCalibrator()
        self.sizer = PositionSizer()
        self.gov_state = GovernorState()
        self._last_trade_ts = 0.0

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

        ok, why = self.risk_governor.check(self.gov_state, nav=broker_ctx.nav)
        if not ok:
            trace = self.events.new_trace()
            self.events.emit("risk_blocked", trace, {"reason": why})
            return []

        decisions = []
        for instrument in self.settings.instruments:
            bars = market_data.get_recent_bars(instrument, self.settings.granularity, count=150)
            if len(bars) < 40:
                continue
            spread_pctile = market_data.get_spread_pctile(instrument)
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
            if decision.get("approved"):
                self._last_trade_ts = now
                self.gov_state.trades_today += 1
            decisions.append(decision)
        return decisions
